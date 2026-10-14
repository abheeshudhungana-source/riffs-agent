"""Tests for Suno-style double prompting and Human-in-the-Loop vocal confirmation."""

import os
import sys
import json
import unittest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from agent import RiffsAgent, VocalApprovalError
from riffs_api.prompt_guardrails import PromptRefusal, validate_prompt


class TestLyricsVocalHITL(unittest.TestCase):
    def setUp(self):
        self.agent = RiffsAgent()
        self.prev_secret = os.environ.get("RIFFS_VOCAL_SECRET")
        os.environ["RIFFS_VOCAL_SECRET"] = "test-secret-hitl-2026"

    def tearDown(self):
        if self.prev_secret is None:
            os.environ.pop("RIFFS_VOCAL_SECRET", None)
        else:
            os.environ["RIFFS_VOCAL_SECRET"] = self.prev_secret

    def test_vocal_secret_missing_raises_runtime_error(self):
        os.environ.pop("RIFFS_VOCAL_SECRET", None)
        with self.assertRaises(RuntimeError) as ctx:
            self.agent.generate(
                prompt="Neo-soul",
                chords="Am - F - C - G",
                lyrics_prompt="Driving at night",
                vocal_approved=False,
            )
        self.assertIn("RIFFS_VOCAL_SECRET", str(ctx.exception))

    def test_guardrails_allow_lyrics_when_explicitly_enabled(self):
        # By default, instrumental prompt without lyrics permission rejects lyrics
        with self.assertRaises(PromptRefusal) as ctx:
            validate_prompt("Write lyrics about love", allow_lyrics=False)
        self.assertEqual(ctx.exception.code, "INSTRUMENTAL_ONLY")

        # When allow_lyrics=True, it succeeds
        try:
            validate_prompt("Write lyrics about love", allow_lyrics=True)
        except PromptRefusal:
            self.fail("validate_prompt raised PromptRefusal unexpectedly when allow_lyrics=True")

    def test_guardrails_still_block_full_song_even_if_lyrics_allowed(self):
        with self.assertRaises(PromptRefusal) as ctx:
            validate_prompt("Write a complete song with lyrics", allow_lyrics=True)
        self.assertEqual(ctx.exception.code, "LOOP_LENGTH_LIMIT")

    def test_double_prompt_generates_lyrics_draft_and_halts_at_checkpoint(self):
        # Request with both instrumental prompt and lyrics prompt, but unapproved
        result = self.agent.generate(
            prompt="Neo-soul groove with mellow rhodes",
            chords="Am - F - C - G",
            key="Am",
            bpm=110,
            lyrics_prompt="Late night driving through the city lights",
            lyrics_language="en",
            vocal_style="soulful_lead",
            vocal_approved=False,
        )

        # Must halt at the Human-in-the-Loop checkpoint
        self.assertEqual(result.get("status"), "awaiting_vocal_confirmation")
        self.assertIn("lyrics_draft", result)
        lyrics_draft = result["lyrics_draft"]
        self.assertEqual(lyrics_draft["language"], "en")
        self.assertEqual(lyrics_draft["vocal_style"], "soulful_lead")
        self.assertTrue(len(lyrics_draft["bars"]) >= 4, "Must generate at least 4 bars of lyrics")

        # Each bar must be aligned with the progression chords
        chords = ["Am", "F", "C", "G"]
        for i, bar in enumerate(lyrics_draft["bars"][:4]):
            self.assertEqual(bar["chord"], chords[i % len(chords)])
            self.assertTrue(len(bar["text"]) > 0)

        # Checkpoint response must NOT bypass preview audio or local storage
        self.assertIn("audio_preview", result)
        self.assertEqual(result["audio_preview"]["format"], "wav")
        self.assertIn("data_base64", result["audio_preview"])
        self.assertIn("take_storage", result)
        self.assertIn("storage_id", result["take_storage"])
        self.assertIn("melodic_similarity", result)

        # Must provide a signed confirmation token
        self.assertIn("vocal_confirmation_token", result)
        self.assertTrue(len(result["vocal_confirmation_token"]) > 16)

        # Vocal lead stem must NOT be synthesized or available until approved
        vocal_stems = [s for s in result.get("stems", []) if s.get("lane") == "vocal_lead"]
        self.assertEqual(len(vocal_stems), 0, "Vocal stem must not be published before approval")

    # ---- helpers -------------------------------------------------------------------
    def _checkpoint(self, prompt="Soul pocket", chords="Am - F - C - G",
                    lyrics_prompt="Rain on the windowpane", **kwargs):
        return self.agent.generate(
            prompt=prompt, chords=chords, lyrics_prompt=lyrics_prompt,
            vocal_approved=False, **kwargs,
        )

    def _approve(self, checkpoint, lines=None, prompt="Soul pocket", chords="Am - F - C - G",
                 lyrics_prompt="Rain on the windowpane", token=None, **kwargs):
        lines = lines if lines is not None else [b["text"] for b in checkpoint["lyrics_draft"]["bars"]]
        kwargs.setdefault("acknowledge_unassessed_rights", True)
        return RiffsAgent().generate(
            prompt=prompt, chords=chords, lyrics_prompt=lyrics_prompt,
            vocal_approved=True,
            vocal_approval_token=token or checkpoint["vocal_confirmation_token"],
            edited_lyrics=lines, **kwargs,
        )

    def test_checkpoint_rejection_with_invalid_or_missing_token(self):
        # A forged token must be rejected even when exact lyrics are supplied
        with self.assertRaises(VocalApprovalError) as ctx:
            self.agent.generate(
                prompt="Neo-soul",
                chords="Am - F - C - G",
                lyrics_prompt="Driving at night",
                vocal_approved=True,
                vocal_approval_token="FORGED_INVALID_TOKEN",
                edited_lyrics=["a", "b", "c", "d"],
                acknowledge_unassessed_rights=True,
            )
        self.assertEqual(ctx.exception.code, "TOKEN_INVALID")

    def test_checkpoint_approval_synthesizes_vocal_lead(self):
        res1 = self._checkpoint()
        res2 = self._approve(res1)

        self.assertEqual(res2.get("status"), "success")
        self.assertIn("lyrics", res2)
        self.assertEqual(res2["lyrics"][0]["text"], res1["lyrics_draft"]["bars"][0]["text"])

        # Vocal lead stem must now be available in stems and score
        vocal_stems = [s for s in res2.get("stems", []) if s.get("lane") == "vocal_lead"]
        self.assertEqual(len(vocal_stems), 1, "Vocal stem must be present after approval")
        self.assertTrue(vocal_stems[0]["available"])

        vocal_lanes = [l for l in res2["score"]["lanes"] if l.get("instrument") == "vocal_lead"]
        self.assertEqual(len(vocal_lanes), 1)
        self.assertTrue(len(vocal_lanes[0]["events"]) > 0)

    def test_checkpoint_approval_with_edited_plain_string_lines(self):
        custom_lines = [
            "Walking alone under neon signs",
            "Shadows dance along the street",
            "Waiting for a rhythm in the night",
            "Moving with the bass guitar beat"
        ]
        common = dict(prompt="Funky groove", chords="Dm - G - C - Am", lyrics_prompt="City lights flickering")
        # Edits go back through the checkpoint so the new token is bound to the edited text.
        res1 = self._checkpoint(**common, edited_lyrics=custom_lines)
        self.assertEqual([b["text"] for b in res1["lyrics_draft"]["bars"]], custom_lines)

        res2 = self._approve(res1, lines=custom_lines, **common)

        self.assertEqual(res2.get("status"), "success")
        self.assertEqual(len(res2["lyrics"]), 4)
        self.assertEqual(res2["lyrics"][0]["text"], "Walking alone under neon signs")
        self.assertEqual(res2["lyrics"][0]["chord"], "Dm")

    def test_multilingual_lyrics_generation(self):
        for lang, expected_token in [("es", "noche"), ("fr", "nuit"), ("ja", "夜")]:
            res = self.agent.generate(
                prompt="Latin jazz groove",
                chords="Am - Dm - E7 - Am",
                lyrics_prompt="Sol y sombra",
                lyrics_language=lang,
                vocal_approved=False,
            )
            self.assertEqual(res.get("status"), "awaiting_vocal_confirmation")
            lyrics = res["lyrics_draft"]["bars"]
            text_corpus = " ".join(b["text"] for b in lyrics)
            self.assertIn(expected_token, text_corpus, f"Expected {expected_token} in {lang} lyrics")

    def test_api_vocal_approval_endpoint(self):
        from fastapi.testclient import TestClient
        from app import app

        client = TestClient(app)

        # 1. First request generates instrumental backing and halts for vocal confirmation
        req1 = client.post("/api/generate", json={
            "prompt": "Smooth soul groove",
            "key": "Am",
            "bpm": 110,
            "chords": "Am - F - C - G",
            "instruments": ["bass_guitar", "rhythm_guitar", "drum_kit"],
            "lyrics_prompt": "Midnight train arriving at dawn",
            "lyrics_language": "en",
            "vocal_style": "soulful_lead",
            "vocal_approved": False,
        })
        self.assertEqual(req1.status_code, 200)
        d1 = req1.json()["data"]
        self.assertEqual(d1["status"], "awaiting_vocal_confirmation")
        token = d1["vocal_confirmation_token"]

        # 2. Forged token must be rejected with 403
        bad_req = client.post("/api/vocals/approve", json={
            "token": "FORGED_SIGNATURE_TOKEN",
            "lyrics_prompt": "Midnight train arriving at dawn",
            "key": "Am",
            "bpm": 110,
            "chords": "Am - F - C - G",
        })
        self.assertEqual(bad_req.status_code, 403)

        # 3. Approval without the rights acknowledgment is refused (rights are unassessed here)
        base = {
            "token": token,
            "prompt": "Smooth soul groove",
            "lyrics_prompt": "Midnight train arriving at dawn",
            "key": "Am",
            "bpm": 110,
            "chords": "Am - F - C - G",
            "instruments": ["bass_guitar", "rhythm_guitar", "drum_kit"],
            "edited_lyrics": [b["text"] for b in d1["lyrics_draft"]["bars"]],
        }
        no_ack = client.post("/api/vocals/approve", json=base)
        self.assertEqual(no_ack.status_code, 403)
        self.assertEqual(no_ack.json()["code"], "RIGHTS_ACK_REQUIRED")

        # 4. Legitimate approval (with acknowledgment) succeeds and synthesizes vocal lead
        ok_req = client.post("/api/vocals/approve", json={**base, "acknowledge_unassessed_rights": True})
        self.assertEqual(ok_req.status_code, 200)
        d2 = ok_req.json()["data"]
        self.assertEqual(d2["status"], "success")
        self.assertIn("vocal_lead", [s["lane"] for s in d2["stems"]])
        vocal_lanes = [l for l in d2["score"]["lanes"] if l["instrument"] == "vocal_lead"]
        self.assertEqual(len(vocal_lanes), 1)

        # 5. The same token cannot be replayed
        replay = client.post("/api/vocals/approve", json={**base, "acknowledge_unassessed_rights": True})
        self.assertEqual(replay.status_code, 403)
        self.assertEqual(replay.json()["code"], "TOKEN_REPLAYED")

    def test_lyrics_strictly_limited_to_four_line_verse(self):
        # 4-chord progression
        res1 = self.agent.generate(
            prompt="Neo-soul groove",
            chords="Am - F - C - G",
            lyrics_prompt="Reflections in the river",
            vocal_approved=False,
        )
        self.assertEqual(len(res1["lyrics_draft"]["bars"]), 4, "Must be strictly 4 lines")

        # 8-chord progression must also be strictly limited to a 4-line verse
        res2 = self.agent.generate(
            prompt="Neo-soul groove",
            chords="Am - F - C - G - Dm - Am - E7 - Am",
            lyrics_prompt="Reflections in the river",
            vocal_approved=False,
        )
        self.assertEqual(len(res2["lyrics_draft"]["bars"]), 4, "8-chord progression must still limit verse to 4 lines")

        # After approval, result must also be strictly 4 lines
        approved = self._approve(res1, prompt="Neo-soul groove", lyrics_prompt="Reflections in the river")
        self.assertEqual(len(approved["lyrics"]), 4, "Approved lyrics must be strictly 4 lines")

    def test_lyrics_match_instrumental_vibe_reggae(self):
        res = self.agent.generate(
            prompt="Roots reggae dub with one-drop bass",
            chords="Am - G - F - G",
            lyrics_prompt="Freedom and sunshine",
            vocal_approved=False,
        )
        draft = res["lyrics_draft"]
        self.assertEqual(draft["instrumental_vibe"], "reggae")
        self.assertEqual(len(draft["bars"]), 4)
        corpus = " ".join(b["text"].lower() for b in draft["bars"])
        self.assertTrue(any(w in corpus for w in ["dub", "skank", "reggae", "one drop", "vibrations"]))

    def test_lyrics_match_instrumental_vibe_blues(self):
        res = self.agent.generate(
            prompt="Gritty delta blues shuffle with dobro resonator",
            chords="E7 - A7 - E7 - B7",
            lyrics_prompt="Crossroads at dawn",
            vocal_approved=False,
        )
        draft = res["lyrics_draft"]
        self.assertEqual(draft["instrumental_vibe"], "blues")
        self.assertEqual(len(draft["bars"]), 4)
        corpus = " ".join(b["text"].lower() for b in draft["bars"])
        self.assertTrue(any(w in corpus for w in ["resonator", "blues", "dust", "shuffle", "boots"]))

    def test_lyrics_match_instrumental_vibe_neosoul(self):
        res = self.agent.generate(
            prompt="Smooth neo-soul groove with warm rhodes",
            chords="Am7 - Dm7 - G7 - Cmaj7",
            lyrics_prompt="Stargazing by the lake",
            vocal_approved=False,
        )
        draft = res["lyrics_draft"]
        self.assertEqual(draft["instrumental_vibe"], "neosoul")
        self.assertEqual(len(draft["bars"]), 4)
        corpus = " ".join(b["text"].lower() for b in draft["bars"])
        self.assertTrue(any(w in corpus for w in ["rhodes", "velvet", "soul", "sunset"]))

    def test_lyrics_match_instrumental_vibe_funk(self):
        res = self.agent.generate(
            prompt="Upbeat funk with slap bass pocket",
            chords="E9 - A13 - E9 - B7",
            lyrics_prompt="Get on the dancefloor",
            vocal_approved=False,
        )
        draft = res["lyrics_draft"]
        self.assertEqual(draft["instrumental_vibe"], "funk")
        self.assertEqual(len(draft["bars"]), 4)
        corpus = " ".join(b["text"].lower() for b in draft["bars"])
        self.assertTrue(any(w in corpus for w in ["slap", "funk", "disco", "tight", "pocket"]))

    def test_token_rejects_edited_draft_with_original_token(self):
        # A checkpoint is issued for draft A
        res1 = self._checkpoint(prompt="Neo-soul groove", lyrics_prompt="Starlight shining")
        original_token = res1["vocal_confirmation_token"]
        original_lines = [b["text"] for b in res1["lyrics_draft"]["bars"]]

        # Attempt to approve with edited lines without acquiring a fresh token
        tampered_lines = list(original_lines)
        tampered_lines[0] = "Tampered first line not in token"

        with self.assertRaises(VocalApprovalError) as ctx:
            self._approve(res1, lines=tampered_lines, prompt="Neo-soul groove",
                          lyrics_prompt="Starlight shining", token=original_token)
        self.assertEqual(ctx.exception.code, "LYRICS_MISMATCH")

    def test_token_rejects_altered_context(self):
        res1 = self._checkpoint(prompt="Neo-soul groove", chords="Am - F - C - G", key="Am")
        token = res1["vocal_confirmation_token"]
        lines = [b["text"] for b in res1["lyrics_draft"]["bars"]]

        # Try approving with altered key
        with self.assertRaises(VocalApprovalError) as ctx:
            self.agent.generate(
                prompt="Neo-soul groove",
                chords="Am - F - C - G",
                key="Dm",  # altered key
                bpm=110,
                lyrics_prompt="Rain on the windowpane",
                vocal_approved=True,
                vocal_approval_token=token,
                edited_lyrics=lines,
                acknowledge_unassessed_rights=True,
            )
        self.assertEqual(ctx.exception.code, "CONTEXT_MISMATCH")

    def test_token_rejects_expired_token(self):
        from agent import generate_vocal_token, build_vocal_context
        import time

        lyrics = ["Line 1", "Line 2", "Line 3", "Line 4"]
        ctx = build_vocal_context("Am", 110, ["Am", "F", "C", "G"], "straight",
                                  ["bass_guitar"], "Prompt", "en", "soulful_lead", "Soul groove")
        # Generate token with negative TTL (already expired)
        expired_token = generate_vocal_token(lyrics, ctx, "unassessed", ttl_seconds=-10)

        with self.assertRaises(VocalApprovalError) as ctx_err:
            self.agent.generate(
                prompt="Soul groove",
                chords="Am - F - C - G",
                key="Am",
                bpm=110,
                instruments=["bass_guitar"],
                lyrics_prompt="Prompt",
                vocal_approved=True,
                vocal_approval_token=expired_token,
                edited_lyrics=lyrics,
                acknowledge_unassessed_rights=True,
            )
        self.assertEqual(ctx_err.exception.code, "TOKEN_EXPIRED")

    def test_token_rejects_replayed_token_agent_level(self):
        res1 = self._checkpoint(prompt="Soul groove", chords="Am - F - C - G")
        token = res1["vocal_confirmation_token"]
        lines = [b["text"] for b in res1["lyrics_draft"]["bars"]]

        # First consumption succeeds
        res2 = self._approve(res1, lines=lines, prompt="Soul groove", chords="Am - F - C - G", token=token)
        self.assertEqual(res2.get("status"), "success")

        # Second consumption with the exact same token fails
        with self.assertRaises(VocalApprovalError) as ctx:
            self._approve(res1, lines=lines, prompt="Soul groove", chords="Am - F - C - G", token=token)
        self.assertEqual(ctx.exception.code, "TOKEN_REPLAYED")

    def test_rights_outcome_potential_match_rejected(self):
        from agent import generate_vocal_token, build_vocal_context

        lyrics = ["Line 1", "Line 2", "Line 3", "Line 4"]
        ctx = build_vocal_context("Am", 110, ["Am", "F", "C", "G"], "straight",
                                  ["bass_guitar"], "Prompt", "en", "soulful_lead", "Soul groove")
        # Token issued when a potential match was flagged
        matched_token = generate_vocal_token(lyrics, ctx, "possible_match")

        with self.assertRaises(VocalApprovalError) as ctx_err:
            self.agent.generate(
                prompt="Soul groove",
                chords="Am - F - C - G",
                key="Am",
                bpm=110,
                instruments=["bass_guitar"],
                lyrics_prompt="Prompt",
                vocal_approved=True,
                vocal_approval_token=matched_token,
                edited_lyrics=lyrics,
                acknowledge_unassessed_rights=True,
            )
        self.assertEqual(ctx_err.exception.code, "POTENTIAL_MATCH")

    def test_rights_outcome_unassessed_requires_acknowledgment(self):
        res1 = self._checkpoint(prompt="Soul groove", chords="Am - F - C - G")
        token = res1["vocal_confirmation_token"]
        lines = [b["text"] for b in res1["lyrics_draft"]["bars"]]

        # Approval without acknowledge_unassessed_rights raises RIGHTS_ACK_REQUIRED
        with self.assertRaises(VocalApprovalError) as ctx:
            self.agent.generate(
                prompt="Soul groove",
                chords="Am - F - C - G",
                key="Am",
                bpm=110,
                lyrics_prompt="Rain on the windowpane",
                vocal_approved=True,
                vocal_approval_token=token,
                edited_lyrics=lines,
                acknowledge_unassessed_rights=False,
            )
        self.assertEqual(ctx.exception.code, "RIGHTS_ACK_REQUIRED")

        # Approval with acknowledgment succeeds
        res2 = self.agent.generate(
            prompt="Soul groove",
            chords="Am - F - C - G",
            key="Am",
            bpm=110,
            lyrics_prompt="Rain on the windowpane",
            vocal_approved=True,
            vocal_approval_token=token,
            edited_lyrics=lines,
            acknowledge_unassessed_rights=True,
        )
        self.assertEqual(res2.get("status"), "success")

    def test_rights_outcome_clean_corpus_succeeds_without_ack(self):
        from agent import generate_vocal_token, build_vocal_context

        lyrics = ["Line 1", "Line 2", "Line 3", "Line 4"]
        ctx = build_vocal_context("Am", 110, ["Am", "F", "C", "G"], "straight",
                                  ["bass_guitar"], "Clean test", "en", "soulful_lead", "Clean test")
        # Token issued with clean rights status
        clean_token = generate_vocal_token(lyrics, ctx, "clean")

        from unittest.mock import patch
        # Patch derive_rights_status to return clean during verification
        with patch("agent.derive_rights_status", return_value="clean"):
            res = self.agent.generate(
                prompt="Clean test",
                chords="Am - F - C - G",
                key="Am",
                bpm=110,
                instruments=["bass_guitar"],
                lyrics_prompt="Clean test",
                vocal_approved=True,
                vocal_approval_token=clean_token,
                edited_lyrics=lyrics,
                acknowledge_unassessed_rights=False,  # No ack required when clean!
            )
        self.assertEqual(res.get("status"), "success")

    def test_token_store_fail_closed_on_vercel_without_kv(self):
        from riffs_api.token_store import get_token_store, TokenStoreUnavailable, set_token_store
        import riffs_api.token_store as ts

        # Reset singleton
        ts._GLOBAL_STORE = None

        prev_vercel = os.environ.get("VERCEL")
        prev_kv_url = os.environ.get("KV_REST_API_URL")
        prev_upstash_url = os.environ.get("UPSTASH_REDIS_REST_URL")
        try:
            os.environ["VERCEL"] = "1"
            os.environ.pop("KV_REST_API_URL", None)
            os.environ.pop("UPSTASH_REDIS_REST_URL", None)

            with self.assertRaises(TokenStoreUnavailable) as ctx:
                get_token_store()
            self.assertIn("KV_REST_API_URL", str(ctx.exception))
        finally:
            if prev_vercel is not None:
                os.environ["VERCEL"] = prev_vercel
            else:
                os.environ.pop("VERCEL", None)
            if prev_kv_url:
                os.environ["KV_REST_API_URL"] = prev_kv_url
            if prev_upstash_url:
                os.environ["UPSTASH_REDIS_REST_URL"] = prev_upstash_url
            ts._GLOBAL_STORE = None

    def test_upstash_redis_token_store_atomic_nx(self):
        from riffs_api.token_store import UpstashRedisTokenStore
        from unittest.mock import patch, MagicMock
        import io

        store = UpstashRedisTokenStore(url="https://fake-kv.upstash.io", token="secret-token")

        # Mock urllib.request.urlopen returning {"result": "OK"} for first call
        mock_response_ok = MagicMock()
        mock_response_ok.read.return_value = json.dumps({"result": "OK"}).encode("utf-8")
        mock_response_ok.__enter__.return_value = mock_response_ok

        # And returning {"result": None} (key already existed) for second call
        mock_response_none = MagicMock()
        mock_response_none.read.return_value = json.dumps({"result": None}).encode("utf-8")
        mock_response_none.__enter__.return_value = mock_response_none

        with patch("urllib.request.urlopen", side_effect=[mock_response_ok, mock_response_none]) as mock_urlopen:
            first_use = store.consume_token("test-jti-123", 1700000000)
            self.assertTrue(first_use)

            # Check that request payload was ["SET", "riffs:vocal:token:test-jti-123", "consumed", "EXAT", 1700000060, "NX"]
            req = mock_urlopen.call_args_list[0][0][0]
            self.assertEqual(req.full_url, "https://fake-kv.upstash.io")
            sent_payload = json.loads(req.data.decode("utf-8"))
            self.assertEqual(sent_payload, ["SET", "riffs:vocal:token:test-jti-123", "consumed", "EXAT", 1700000060, "NX"])
            self.assertEqual(req.headers["Authorization"], "Bearer secret-token")

            # Second call returns False (replay detected)
            second_use = store.consume_token("test-jti-123", 1700000000)
            self.assertFalse(second_use)


if __name__ == "__main__":
    unittest.main()


