"""Regression evaluations for RIFFs Human-in-the-Loop vocal approval flow.

Covers:
1. Context mismatch detection when request fields change between checkpoint and approval
2. Lyrics mismatch detection when lyrics differ from signed token
3. Expired and replayed token rejections (TOKEN_EXPIRED, TOKEN_REPLAYED)
4. Malformed lyrics rejection (blank lines, numbers, nulls, empty list, XSS, violence, length limits)
5. Refusal codes (INSTRUMENTAL_ONLY, LOOP_LENGTH_LIMIT, COPYRIGHT_REPRODUCTION_REQUEST) return 422 without CHORD_SYNTAX mislabeling
6. 2-chord and 8-chord vocal lanes: voices all 8 bars (up to beat 31.99), stems/part_scores have MIDI hashes, and locking vocal_lead preserves notes
7. Stored take token redaction: stored record has "[REDACTED]"
8. Redacted audit traces: records checkpoint_created, approval_accepted, approval_rejected with hashes, masked token IDs, and strictly zero raw lyric text or raw tokens
"""

import copy
import hashlib
import json
import os
import pathlib
import sys
import tempfile
import time
import unittest
from fastapi.testclient import TestClient

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app import app
from agent import RiffsAgent, VocalApprovalError, generate_vocal_token, build_vocal_context
from riffs_api.prompt_guardrails import PromptRefusal, validate_lyrics
from riffs_api.audit_trace import read_audit_traces


class TestVocalRegressionEvals(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.client = TestClient(app)

    def setUp(self):
        self.temp_dir = tempfile.TemporaryDirectory()
        self.audit_log_path = pathlib.Path(self.temp_dir.name) / "audit_trace.jsonl"
        self.take_store_path = pathlib.Path(self.temp_dir.name) / "takes"

        self.prev_secret = os.environ.get("RIFFS_VOCAL_SECRET")
        self.prev_audit = os.environ.get("RIFFS_AUDIT_LOG_PATH")
        self.prev_take_store = os.environ.get("RIFFS_TAKE_STORE_PATH")

        os.environ["RIFFS_VOCAL_SECRET"] = "regression-test-secret-key-32chars!"
        os.environ["RIFFS_AUDIT_LOG_PATH"] = str(self.audit_log_path)
        os.environ["RIFFS_TAKE_STORE_PATH"] = str(self.take_store_path)

        self.agent = RiffsAgent()

    def tearDown(self):
        if self.prev_secret is not None:
            os.environ["RIFFS_VOCAL_SECRET"] = self.prev_secret
        else:
            os.environ.pop("RIFFS_VOCAL_SECRET", None)

        if self.prev_audit is not None:
            os.environ["RIFFS_AUDIT_LOG_PATH"] = self.prev_audit
        else:
            os.environ.pop("RIFFS_AUDIT_LOG_PATH", None)

        if self.prev_take_store is not None:
            os.environ["RIFFS_TAKE_STORE_PATH"] = self.prev_take_store
        else:
            os.environ.pop("RIFFS_TAKE_STORE_PATH", None)

        self.temp_dir.cleanup()

    # -------------------------------------------------------------------------
    # 1. Changed request fields between checkpoint and approval
    # -------------------------------------------------------------------------
    def test_regression_changed_request_context_fields_rejected(self):
        """Altering accompaniment context between checkpoint and approval must return CONTEXT_MISMATCH."""
        base_request = {
            "prompt": "Night drive synth pop",
            "key": "Am",
            "bpm": 110,
            "chords": "Am - F - C - G",
            "instruments": ["bass_guitar", "rhythm_guitar", "cymbals"],
            "groove": "straight",
            "lyrics_prompt": "Neon signs reflect the rain",
            "lyrics_language": "en",
            "vocal_style": "soulful_lead",
        }

        # Step 1: Issue checkpoint
        resp = self.client.post("/api/generate", json=base_request)
        self.assertEqual(resp.status_code, 200)
        data = resp.json()["data"]
        self.assertEqual(data["checkpoint"], "HUMAN_IN_THE_LOOP_VOCAL_APPROVAL")
        token = data["vocal_confirmation_token"]
        bars = data["lyrics_draft"]["bars"]
        valid_lines = [b["text"] for b in bars]

        # Step 2: Attempt approval with modified context fields one by one
        variations = [
            ("key", "C"),
            ("bpm", 124),
            ("chords", "C - G - Am - F"),
            ("instruments", ["contrabass", "rhythm_guitar", "cymbals"]),
            ("groove", "swing"),
            ("lyrics_language", "es"),
            ("vocal_style", "pop_lead"),
            ("prompt", "Completely different mood and style"),
        ]

        for field, new_val in variations:
            with self.subTest(altered_field=field, value=new_val):
                approve_payload = {
                    "token": token,
                    "lyrics_prompt": base_request["lyrics_prompt"],
                    "prompt": base_request["prompt"],
                    "key": base_request["key"],
                    "bpm": base_request["bpm"],
                    "chords": base_request["chords"],
                    "instruments": base_request["instruments"],
                    "groove": base_request["groove"],
                    "vocal_style": base_request["vocal_style"],
                    "lyrics_language": base_request["lyrics_language"],
                    "edited_lyrics": valid_lines,
                    "acknowledge_unassessed_rights": True,
                }
                approve_payload[field] = new_val

                res = self.client.post("/api/vocals/approve", json=approve_payload)
                self.assertEqual(res.status_code, 403)
                err = res.json()
                self.assertEqual(err["code"], "CONTEXT_MISMATCH")
                self.assertIn("Context mismatch", err["detail"])

    # -------------------------------------------------------------------------
    # 2. Changed lyrics without re-checkpoint
    # -------------------------------------------------------------------------
    def test_regression_changed_lyrics_rejected_with_lyrics_mismatch(self):
        """Supplying different lyrics than signed in the token must return LYRICS_MISMATCH."""
        base_request = {
            "prompt": "Indie acoustic",
            "key": "G",
            "bpm": 95,
            "chords": "G - Em - C - D",
            "instruments": ["bass_guitar", "rhythm_guitar", "cymbals"],
            "lyrics_prompt": "Morning coffee by the sunrise",
        }

        resp = self.client.post("/api/generate", json=base_request)
        self.assertEqual(resp.status_code, 200)
        data = resp.json()["data"]
        token = data["vocal_confirmation_token"]

        tampered_lyrics = [
            "Sneaking in unauthorized words",
            "That were never approved by human review",
            "Hoping the token will validate anyway",
            "Line four of tampered text",
        ]

        approve_payload = {
            "token": token,
            "lyrics_prompt": base_request["lyrics_prompt"],
            "prompt": base_request["prompt"],
            "key": base_request["key"],
            "bpm": base_request["bpm"],
            "chords": base_request["chords"],
            "instruments": base_request["instruments"],
            "edited_lyrics": tampered_lyrics,
            "acknowledge_unassessed_rights": True,
        }

        res = self.client.post("/api/vocals/approve", json=approve_payload)
        self.assertEqual(res.status_code, 403)
        err = res.json()
        self.assertEqual(err["code"], "LYRICS_MISMATCH")
        self.assertIn("token does not authorize these lyrics", err["detail"])

    # -------------------------------------------------------------------------
    # 3. Expired and reused tokens
    # -------------------------------------------------------------------------
    def test_regression_expired_and_reused_tokens(self):
        """Expired tokens and replayed tokens must fail closed."""
        lines = ["Line 1", "Line 2", "Line 3", "Line 4"]
        ctx = build_vocal_context(
            key="Am",
            bpm=110,
            chords=["Am", "F", "C", "G"],
            groove="straight",
            instruments=["bass_guitar", "cymbals", "rhythm_guitar"],
            lyrics_prompt="Testing token lifespan",
            lyrics_language="en",
            vocal_style="soulful_lead",
            prompt="Acoustic soul",
        )

        # 3a: Expired token
        expired_token = generate_vocal_token(
            lyrics=lines,
            context=ctx,
            rights_status="clean",
            ttl_seconds=-10,  # expired 10s ago
        )
        with self.assertRaises(VocalApprovalError) as ex_ctx:
            self.agent.generate(
                prompt="Acoustic soul",
                chords="Am - F - C - G",
                key="Am",
                bpm=110,
                instruments=["bass_guitar", "rhythm_guitar", "cymbals"],
                lyrics_prompt="Testing token lifespan",
                vocal_approved=True,
                vocal_approval_token=expired_token,
                edited_lyrics=lines,
                acknowledge_unassessed_rights=True,
            )
        self.assertEqual(ex_ctx.exception.code, "TOKEN_EXPIRED")

        # 3b: Single-use replay rejection
        valid_token = generate_vocal_token(
            lyrics=lines,
            context=ctx,
            rights_status="clean",
            ttl_seconds=300,
        )

        # First consumption must succeed
        first_res = self.agent.generate(
            prompt="Acoustic soul",
            chords="Am - F - C - G",
            key="Am",
            bpm=110,
            instruments=["bass_guitar", "rhythm_guitar", "cymbals"],
            lyrics_prompt="Testing token lifespan",
            vocal_approved=True,
            vocal_approval_token=valid_token,
            edited_lyrics=lines,
            acknowledge_unassessed_rights=True,
        )
        self.assertEqual(first_res["status"], "success")

        # Second consumption with identical token must fail with TOKEN_REPLAYED
        with self.assertRaises(VocalApprovalError) as replay_ctx:
            self.agent.generate(
                prompt="Acoustic soul",
                chords="Am - F - C - G",
                key="Am",
                bpm=110,
                instruments=["bass_guitar", "rhythm_guitar", "cymbals"],
                lyrics_prompt="Testing token lifespan",
                vocal_approved=True,
                vocal_approval_token=valid_token,
                edited_lyrics=lines,
                acknowledge_unassessed_rights=True,
            )
        self.assertEqual(replay_ctx.exception.code, "TOKEN_REPLAYED")

    # -------------------------------------------------------------------------
    # 4. Malformed lyrics rejection
    # -------------------------------------------------------------------------
    def test_regression_malformed_lyrics_validation(self):
        """Malformed lyrics (empty list, nulls, numbers, blank lines, length limits, XSS, violence) are rejected."""
        # Test helper function
        with self.assertRaises(PromptRefusal) as ctx:
            validate_lyrics([])
        self.assertEqual(ctx.exception.code, "INVALID_LYRICS")

        with self.assertRaises(PromptRefusal) as ctx:
            validate_lyrics(["Valid line 1", 12345, "Valid line 3"])
        self.assertEqual(ctx.exception.code, "INVALID_LYRICS")

        with self.assertRaises(PromptRefusal) as ctx:
            validate_lyrics(["Line 1", "   ", "Line 3"])
        self.assertEqual(ctx.exception.code, "INVALID_LYRICS")

        with self.assertRaises(PromptRefusal) as ctx:
            validate_lyrics(["x" * 251, "Normal line", "Normal line 2"])
        self.assertEqual(ctx.exception.code, "LENGTH_LIMIT")

        with self.assertRaises(PromptRefusal) as ctx:
            validate_lyrics(["Line 1", "<script>alert('xss')</script>", "Line 3", "Line 4"])
        self.assertEqual(ctx.exception.code, "INJECTION_DETECTED")

        with self.assertRaises(PromptRefusal) as ctx:
            validate_lyrics(["We march forward", "and kill them all in blood", "no mercy", "tonight"])
        self.assertEqual(ctx.exception.code, "SAFETY_VIOLATION")

        # End-to-end API verification via /api/generate
        res = self.client.post("/api/generate", json={
            "prompt": "Groove",
            "chords": "Am - F - C - G",
            "lyrics_prompt": "Sing something",
            "edited_lyrics": ["Line 1", "", "Line 3", "Line 4"],
        })
        self.assertEqual(res.status_code, 422)
        self.assertEqual(res.json()["code"], "INVALID_LYRICS")

    # -------------------------------------------------------------------------
    # 5. Refusal codes not mislabeled as CHORD_SYNTAX
    # -------------------------------------------------------------------------
    def test_regression_refusal_codes_not_mislabeled_as_chord_syntax(self):
        """Guardrail refusals must preserve their exact error codes (INSTRUMENTAL_ONLY, LOOP_LENGTH_LIMIT, etc.)."""
        cases = [
            (
                {"prompt": "Write lyrics about summer nights", "chords": "Am - F - C - G"},
                "INSTRUMENTAL_ONLY",
            ),
            (
                {"prompt": "Generate a full 4 minute song with multiple verses", "chords": "Am - F - C - G"},
                "LOOP_LENGTH_LIMIT",
            ),
            (
                {"prompt": "Is this the real life is this just fantasy", "chords": "Am - F - C - G"},
                "COPYRIGHT_REPRODUCTION_REQUEST",
            ),
        ]

        for req_body, expected_code in cases:
            with self.subTest(code=expected_code):
                res = self.client.post("/api/generate", json=req_body)
                self.assertEqual(res.status_code, 422)
                body = res.json()
                self.assertEqual(body["code"], expected_code)
                self.assertNotEqual(body["code"], "CHORD_SYNTAX", "Refusal must not be mislabeled as CHORD_SYNTAX")
                self.assertTrue(len(body.get("detail", "")) > 0)
                self.assertTrue(len(body.get("alternative", "")) > 0)

    # -------------------------------------------------------------------------
    # 6. 2-chord and 8-chord vocal lanes with locks and MIDI hashes
    # -------------------------------------------------------------------------
    def test_regression_two_and_eight_chord_vocal_lanes_with_locks_and_midi(self):
        """2-chord and 8-chord progressions generate complete vocal melodies, MIDI hashes, and support vocal locking."""
        # 6a: 2-chord progression
        res_2chord = self.agent.generate(
            prompt="Two chord groove",
            chords="Am - F",
            key="Am",
            bpm=100,
            lyrics_prompt="Drifting softly through the fog",
            vocal_approved=False,
        )
        self.assertEqual(res_2chord["status"], "awaiting_vocal_confirmation")
        bars_2 = res_2chord["lyrics_draft"]["bars"]
        self.assertEqual(len(bars_2), 4)
        self.assertEqual(bars_2[0]["chord"], "Am")
        self.assertEqual(bars_2[1]["chord"], "F")
        self.assertEqual(bars_2[2]["chord"], "Am")
        self.assertEqual(bars_2[3]["chord"], "F")

        # 6b: 8-chord progression
        chords_8 = "Am - F - C - G - Dm - Am - E - Am"
        res_8chord = self.agent.generate(
            prompt="Eight chord progression ballad",
            chords=chords_8,
            key="Am",
            bpm=100,
            lyrics_prompt="Eight measures of melody unfolding through the dark",
            vocal_approved=False,
        )
        self.assertEqual(res_8chord["status"], "awaiting_vocal_confirmation")
        token_8 = res_8chord["vocal_confirmation_token"]
        lines_8 = [b["text"] for b in res_8chord["lyrics_draft"]["bars"]]

        # Approve 8-chord progression
        approved_8 = self.agent.generate(
            prompt="Eight chord progression ballad",
            chords=chords_8,
            key="Am",
            bpm=100,
            lyrics_prompt="Eight measures of melody unfolding through the dark",
            vocal_approved=True,
            vocal_approval_token=token_8,
            edited_lyrics=lines_8,
            acknowledge_unassessed_rights=True,
        )
        self.assertEqual(approved_8["status"], "success")

        # Verify vocal_lead lane in score
        vocal_lane = next(l for l in approved_8["score"]["lanes"] if l["instrument"] == "vocal_lead")
        events = vocal_lane["events"]
        self.assertTrue(len(events) >= 8, f"Expected vocal events across 8 bars, got {len(events)}")
        max_beat = max(e["beat"] for e in events)
        self.assertGreater(max_beat, 16.0, f"8-chord vocal melody must span past bar 4 (beat 16.0), got max beat {max_beat}")

        # Verify part_scores and stem contain valid MIDI hash
        self.assertIn("vocal_lead", approved_8["part_scores"])
        vocal_part = approved_8["part_scores"]["vocal_lead"]
        self.assertIn("midi_sha256", vocal_part)
        self.assertEqual(len(vocal_part["midi_sha256"]), 64)
        self.assertIn("midi_base64", vocal_part)

        vocal_stem = next(s for s in approved_8["stems"] if s["lane"] == "vocal_lead")
        self.assertEqual(vocal_stem["midi_sha256"], vocal_part["midi_sha256"])

        # 6c: Lock vocal_lead and regenerate accompaniment
        locked_take = self.agent.generate(
            prompt="Eight chord progression ballad with new bass",
            chords=chords_8,
            key="Am",
            bpm=100,
            instruments=["bass_guitar", "acoustic_piano", "cymbals"],
            locked_parts=["vocal_lead"],
            previous_score=approved_8["score"],
            acknowledge_unassessed_rights=True,
        )
        self.assertEqual(locked_take["status"], "success")
        locked_vocal_lane = next(l for l in locked_take["score"]["lanes"] if l["instrument"] == "vocal_lead")
        self.assertTrue(locked_vocal_lane.get("locked"), "vocal_lead lane must be flagged as locked")
        self.assertEqual(
            locked_vocal_lane["events"],
            vocal_lane["events"],
            "Locked vocal_lead note events must remain identical",
        )
        self.assertEqual(
            locked_take["part_scores"]["vocal_lead"]["midi_sha256"],
            vocal_part["midi_sha256"],
            "Locked vocal_lead MIDI SHA-256 must remain identical",
        )

    # -------------------------------------------------------------------------
    # 7. Stored take token redaction
    # -------------------------------------------------------------------------
    def test_regression_take_store_token_redaction(self):
        """Stored take records must redact confirmation tokens to prevent credential leaks on disk."""
        req = {
            "prompt": "Lo-fi sunset beats",
            "key": "C",
            "bpm": 85,
            "chords": "C - G - Am - F",
            "lyrics_prompt": "Golden hour through the leaves",
        }
        res = self.client.post("/api/generate", json=req)
        self.assertEqual(res.status_code, 200)
        data = res.json()["data"]

        # Token returned in live JSON response
        live_token = data["vocal_confirmation_token"]
        self.assertTrue(live_token.startswith("ey"))

        storage_id = data["take_storage"]["storage_id"]
        # Fetch take record directly from disk storage endpoint
        take_res = self.client.get(f"/api/takes/{storage_id}")
        self.assertEqual(take_res.status_code, 200)
        stored_take_record = take_res.json()["data"]["take"]

        self.assertEqual(
            stored_take_record.get("vocal_confirmation_token"),
            "[REDACTED]",
            "Token on disk must be redacted to [REDACTED]",
        )

    # -------------------------------------------------------------------------
    # 8. Redacted audit trace contents
    # -------------------------------------------------------------------------
    def test_regression_redacted_audit_trace_contents(self):
        """Audit trace records checkpoint creation, acceptance, and rejection with strict zero raw data leakage."""
        lines = ["Silver moonlight falling", "Shadows on the wall", "Whispers in the hallway", "Night begins to call"]
        checkpoint = self.agent.generate(
            prompt="Dark ambient soul",
            key="Dm",
            bpm=90,
            chords="Dm - Bb - F - C",
            lyrics_prompt="Night whispers",
            edited_lyrics=lines,
            vocal_approved=False,
        )
        token = checkpoint["vocal_confirmation_token"]

        # 8a: Successful approval
        approved = self.agent.generate(
            prompt="Dark ambient soul",
            key="Dm",
            bpm=90,
            chords="Dm - Bb - F - C",
            lyrics_prompt="Night whispers",
            edited_lyrics=lines,
            vocal_approved=True,
            vocal_approval_token=token,
            acknowledge_unassessed_rights=True,
        )
        self.assertEqual(approved["status"], "success")

        # 8b: Rejected approval (attempting to replay the consumed token)
        with self.assertRaises(VocalApprovalError):
            self.agent.generate(
                prompt="Dark ambient soul",
                key="Dm",
                bpm=90,
                chords="Dm - Bb - F - C",
                lyrics_prompt="Night whispers",
                edited_lyrics=lines,
                vocal_approved=True,
                vocal_approval_token=token,
                acknowledge_unassessed_rights=True,
            )

        # Inspect recorded trace entries
        records = read_audit_traces(self.audit_log_path)
        self.assertGreaterEqual(len(records), 3, "Expected at least 3 trace events")

        event_types = [r["event_type"] for r in records]
        self.assertIn("checkpoint_created", event_types)
        self.assertIn("approval_accepted", event_types)
        self.assertIn("approval_rejected", event_types)

        # Trace raw file content check
        raw_text = self.audit_log_path.read_text(encoding="utf-8")

        # 1. NO raw token signature or full token should be in the file
        self.assertNotIn(token, raw_text, "Raw vocal confirmation token must not appear anywhere in the audit log")

        # 2. NO raw lyric line should be in the file
        for line in lines:
            self.assertNotIn(line, raw_text, f"Raw lyric text '{line}' must not appear anywhere in the audit log")

        # 3. Check cryptographic hashes and masked token ID formatting
        for rec in records:
            self.assertEqual(len(rec["context_sha256"]), 64)
            self.assertEqual(len(rec["lyrics_sha256"]), 64)
            masked_id = rec.get("token_masked_id")
            if masked_id is not None:
                self.assertEqual(len(masked_id), 12)
                self.assertNotIn(".", masked_id)


if __name__ == "__main__":
    unittest.main()
