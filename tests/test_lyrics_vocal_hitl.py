"""Regression coverage for the human-reviewed vocal lane and approval boundary."""

import copy
import os
import sys
import unittest
from unittest.mock import patch

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from agent import RiffsAgent
from riffs_api.prompt_guardrails import PromptRefusal, validate_prompt
from riffs_api.vocal_approval import (
    VocalApprovalUnavailable,
    VocalInputError,
    consume_vocal_token,
    issue_vocal_token,
    normalize_lyrics,
)


class TestLyricsVocalHITL(unittest.TestCase):
    def setUp(self):
        self.secret_patch = patch.dict(os.environ, {
            "RIFFS_VOCAL_SECRET": "test-only-secret-that-is-long-enough-32",
            "ANTHROPIC_API_KEY": "",
        })
        self.secret_patch.start()
        self.agent = RiffsAgent()
        self.agent.api_key = None

    def tearDown(self):
        self.secret_patch.stop()

    def _request(self, *, chords="Am - F - C - G", **overrides):
        request = {
            "prompt": "Original soul loop",
            "key": "Am",
            "bpm": 110,
            "chords": chords,
            "instruments": ["bass_guitar", "rhythm_guitar", "cymbals"],
            "seed": 17,
            "groove": "straight",
            "lyrics_prompt": "Rain on the windowpane",
            "lyrics_language": "en",
            "vocal_style": "soulful_lead",
        }
        request.update(overrides)
        return request

    def _checkpoint(self, **kwargs):
        return self.agent.generate(**self._request(**kwargs))

    def _approve(self, checkpoint, *, edited=None, **kwargs):
        request = self._request(**kwargs)
        result = self.agent.generate(
            **request,
            vocal_approved=True,
            vocal_approval_token=checkpoint["vocal_confirmation_token"],
            lyrics_draft=checkpoint["lyrics_draft"]["bars"],
            edited_lyrics=edited,
            vocal_trace_id=checkpoint["vocal_trace_id"],
        )
        if result["status"] == "awaiting_vocal_confirmation":
            result = self.agent.generate(
                **request,
                vocal_approved=True,
                vocal_approval_token=result["vocal_confirmation_token"],
                lyrics_draft=result["lyrics_draft"]["bars"],
                edited_lyrics=result["lyrics_draft"]["bars"],
                vocal_trace_id=result["vocal_trace_id"],
            )
        return result

    def test_checkpoint_has_no_vocal_lane_and_returns_trace_id(self):
        result = self._checkpoint()
        self.assertEqual(result["status"], "awaiting_vocal_confirmation")
        self.assertTrue(result["vocal_trace_id"])
        self.assertNotIn("take_id", result)
        self.assertFalse(any(stem["lane"] == "vocal_lead" for stem in result["stems"]))
        self.assertNotIn(result["vocal_confirmation_token"], str(self.agent.take_history))

    def test_token_binds_full_context_and_exact_draft(self):
        context = {"trace_id": "trace-a", "prompt": "one", "groove": "straight"}
        lyrics = [{"bar": 1, "chord": "Am", "text": "first draft"}]
        token = issue_vocal_token(context, lyrics)
        self.assertFalse(consume_vocal_token(token, {**context, "groove": "half_time"}, lyrics))
        self.assertFalse(consume_vocal_token(token, context, [{**lyrics[0], "text": "edited"}]))
        self.assertTrue(consume_vocal_token(token, context, lyrics))
        self.assertFalse(consume_vocal_token(token, context, lyrics))

    def test_token_expires(self):
        context = {"trace_id": "expired"}
        lyrics = [{"bar": 1, "chord": "Am", "text": "line"}]
        with patch("riffs_api.vocal_approval.time.time", return_value=1000):
            token = issue_vocal_token(context, lyrics)
        with patch("riffs_api.vocal_approval.time.time", return_value=1601):
            self.assertFalse(consume_vocal_token(token, context, lyrics))

    def test_trace_logs_are_correlated_and_redacted(self):
        context = {"trace_id": "trace-redacted", "prompt": "private prompt"}
        lyrics = [{"bar": 1, "chord": "Am", "text": "private lyric text"}]
        with self.assertLogs("riffs.vocal_approval", level="INFO") as captured:
            token = issue_vocal_token(context, lyrics)
            self.assertTrue(consume_vocal_token(token, context, lyrics))
        log_text = "\\n".join(captured.output)
        self.assertIn("trace-redacted", log_text)
        self.assertIn("checkpoint_issued", log_text)
        self.assertIn("approval_accepted", log_text)
        self.assertIn("draft_sha256", log_text)
        self.assertNotIn("private lyric text", log_text)
        self.assertNotIn(token, log_text)

    def test_missing_secret_disables_vocal_approval_without_revealing_config(self):
        with patch.dict(os.environ, {"RIFFS_VOCAL_SECRET": ""}):
            with self.assertRaisesRegex(VocalApprovalUnavailable, "unavailable"):
                issue_vocal_token({"trace_id": "no-secret"}, [{"bar": 1, "chord": "Am", "text": "line"}])

    def test_edited_draft_requires_a_second_confirmation(self):
        checkpoint = self._checkpoint()
        edited = copy.deepcopy(checkpoint["lyrics_draft"]["bars"])
        edited[0]["text"] = "A changed line under moonlight"
        request = self._request()
        first_approval = self.agent.generate(
            **request,
            vocal_approved=True,
            vocal_approval_token=checkpoint["vocal_confirmation_token"],
            lyrics_draft=checkpoint["lyrics_draft"]["bars"],
            edited_lyrics=edited,
            vocal_trace_id=checkpoint["vocal_trace_id"],
        )
        self.assertEqual(first_approval["status"], "awaiting_vocal_confirmation")
        self.assertFalse(any(stem["lane"] == "vocal_lead" for stem in first_approval["stems"]))
        approved = self.agent.generate(
            **request,
            vocal_approved=True,
            vocal_approval_token=first_approval["vocal_confirmation_token"],
            lyrics_draft=first_approval["lyrics_draft"]["bars"],
            edited_lyrics=first_approval["lyrics_draft"]["bars"],
            vocal_trace_id=first_approval["vocal_trace_id"],
        )
        self.assertEqual(approved["status"], "success")
        self.assertEqual(approved["lyrics"][0]["text"], edited[0]["text"])

    def test_malformed_or_unsafe_edited_lyrics_are_rejected(self):
        chords = ["Am", "F"]
        for bad in ([], ["" , "ok"], [None, "ok"], [{"text": None}, {"lyric": 123}], ["<script>alert(1)</script>", "ok"], ["kill them all", "ok"], ["x" * 181, "ok"]):
            with self.subTest(bad=bad):
                with self.assertRaises(VocalInputError):
                    normalize_lyrics(bad, chords)

    def test_exact_named_lyrics_request_is_refused(self):
        with self.assertRaises(PromptRefusal) as caught:
            validate_prompt("write the exact lyrics of Bohemian Rhapsody verbatim", allow_lyrics=True)
        self.assertEqual(caught.exception.code, "COPYRIGHT_REPRODUCTION_REQUEST")

    def test_vocal_bars_and_midi_metadata_follow_progression_length(self):
        for progression in ("Am - F", "Am - F - C - G - Dm - Em - F - G"):
            with self.subTest(progression=progression):
                checkpoint = self._checkpoint(chords=progression)
                self.assertEqual(len(checkpoint["lyrics_draft"]["bars"]), len(progression.split(" - ")))
                approved = self._approve(checkpoint, chords=progression)
                self.assertEqual(approved["status"], "success")
                self.assertIn("vocal_lead", approved["part_scores"])
                vocal_part = approved["part_scores"]["vocal_lead"]
                self.assertTrue(vocal_part["midi_sha256"])
                stem = next(s for s in approved["stems"] if s["lane"] == "vocal_lead")
                self.assertEqual(stem["midi_sha256"], vocal_part["midi_sha256"])
                self.assertEqual(len(vocal_part["bars"]), len(progression.split(" - ")))

    def test_vocal_lane_lock_reuses_prior_events(self):
        first_checkpoint = self._checkpoint()
        first = self._approve(first_checkpoint)
        first_lane = next(lane for lane in first["score"]["lanes"] if lane["instrument"] == "vocal_lead")
        request = self._request(locked_parts=["vocal_lead"], previous_score=first["score"], seed=18)
        checkpoint = self.agent.generate(**request)
        approved = self.agent.generate(
            **request,
            vocal_approved=True,
            vocal_approval_token=checkpoint["vocal_confirmation_token"],
            lyrics_draft=checkpoint["lyrics_draft"]["bars"],
            edited_lyrics=checkpoint["lyrics_draft"]["bars"],
            vocal_trace_id=checkpoint["vocal_trace_id"],
        )
        next_lane = next(lane for lane in approved["score"]["lanes"] if lane["instrument"] == "vocal_lead")
        self.assertTrue(next_lane["locked"])
        self.assertEqual(next_lane["hash"], first_lane["hash"])

    def test_api_preserves_structured_refusal_code(self):
        try:
            from fastapi.testclient import TestClient
            from app import app
            client = TestClient(app)
        except ImportError as exc:
            self.skipTest(f"API test dependencies are not installed here: {exc}")
        response = client.post("/api/generate", json={"prompt": "Write lyrics about love"})
        self.assertEqual(response.status_code, 422)
        self.assertEqual(response.json()["code"], "INSTRUMENTAL_ONLY")
        self.assertIn("alternative", response.json())


if __name__ == "__main__":
    unittest.main()
