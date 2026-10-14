"""Tests for Suno-style double prompting and Human-in-the-Loop vocal confirmation."""

import os
import sys
import unittest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from agent import RiffsAgent
from riffs_api.prompt_guardrails import PromptRefusal, validate_prompt


class TestLyricsVocalHITL(unittest.TestCase):
    def setUp(self):
        self.agent = RiffsAgent()

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

        # Must provide a signed confirmation token
        self.assertIn("vocal_confirmation_token", result)
        self.assertTrue(len(result["vocal_confirmation_token"]) > 16)

        # Vocal lead stem must NOT be synthesized or available until approved
        vocal_stems = [s for s in result.get("stems", []) if s.get("lane") == "vocal_lead"]
        self.assertEqual(len(vocal_stems), 0, "Vocal stem must not be published before approval")

    def test_checkpoint_rejection_with_invalid_or_missing_token(self):
        # Trying to set vocal_approved=True with a forged token must fail or stay unapproved
        with self.assertRaises(ValueError):
            self.agent.generate(
                prompt="Neo-soul",
                chords="Am - F - C - G",
                lyrics_prompt="Driving at night",
                vocal_approved=True,
                vocal_approval_token="FORGED_INVALID_TOKEN",
            )

    def test_checkpoint_approval_synthesizes_vocal_lead(self):
        # First turn: draft lyrics
        res1 = self.agent.generate(
            prompt="Soul pocket",
            chords="Am - F - C - G",
            lyrics_prompt="Rain on the windowpane",
            vocal_approved=False,
        )
        token = res1["vocal_confirmation_token"]
        lyrics_draft = res1["lyrics_draft"]

        # Human edits line 1:
        edited_bars = list(lyrics_draft["bars"])
        edited_bars[0]["text"] = "Watching rain drop on the glass tonight"

        # Second turn: human confirms with token and edited lyrics
        res2 = self.agent.generate(
            prompt="Soul pocket",
            chords="Am - F - C - G",
            lyrics_prompt="Rain on the windowpane",
            vocal_approved=True,
            vocal_approval_token=token,
            edited_lyrics=edited_bars,
        )

        self.assertEqual(res2.get("status"), "success")
        self.assertIn("lyrics", res2)
        self.assertEqual(res2["lyrics"][0]["text"], "Watching rain drop on the glass tonight")

        # Vocal lead stem must now be available in stems and score
        vocal_stems = [s for s in res2.get("stems", []) if s.get("lane") == "vocal_lead"]
        self.assertEqual(len(vocal_stems), 1, "Vocal stem must be present after approval")
        self.assertTrue(vocal_stems[0]["available"])

        vocal_lanes = [l for l in res2["score"]["lanes"] if l.get("instrument") == "vocal_lead"]
        self.assertEqual(len(vocal_lanes), 1)
        self.assertTrue(len(vocal_lanes[0]["events"]) > 0)

    def test_checkpoint_approval_with_plain_string_lines(self):
        res1 = self.agent.generate(
            prompt="Funky groove",
            chords="Dm - G - C - Am",
            lyrics_prompt="City lights flickering",
            vocal_approved=False,
        )
        token = res1["vocal_confirmation_token"]

        # Human provides edited lyrics as list of plain strings
        custom_lines = [
            "Walking alone under neon signs",
            "Shadows dance along the street",
            "Waiting for a rhythm in the night",
            "Moving with the bass guitar beat"
        ]

        res2 = self.agent.generate(
            prompt="Funky groove",
            chords="Dm - G - C - Am",
            lyrics_prompt="City lights flickering",
            vocal_approved=True,
            vocal_approval_token=token,
            edited_lyrics=custom_lines,
        )

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

        # 3. Legitimate approval succeeds and synthesizes vocal lead
        ok_req = client.post("/api/vocals/approve", json={
            "token": token,
            "lyrics_prompt": "Midnight train arriving at dawn",
            "key": "Am",
            "bpm": 110,
            "chords": "Am - F - C - G",
            "instruments": ["bass_guitar", "rhythm_guitar", "drum_kit"],
            "edited_lyrics": ["Midnight train rolling down the track"],
        })
        self.assertEqual(ok_req.status_code, 200)
        d2 = ok_req.json()["data"]
        self.assertEqual(d2["status"], "success")
        self.assertIn("vocal_lead", [s["lane"] for s in d2["stems"]])
        vocal_lanes = [l for l in d2["score"]["lanes"] if l["instrument"] == "vocal_lead"]
        self.assertEqual(len(vocal_lanes), 1)


if __name__ == "__main__":
    unittest.main()

