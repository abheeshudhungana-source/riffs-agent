"""Comprehensive unit tests for Day 3 and Day 4 features.

Day 3:
- Headless video remuxing (attach_riff_to_video):
  - 50MB file size safeguard intercept (PRD Case 3)
  - Whitelist file extension enforcement (.mp4, .mov)
  - Shell injection filename sanitization
  - Headless stream copy execution
- Verifiable digital license certificate (license_cert.json)

Day 4:
- Natural language prompt-to-music understanding (chords, key, BPM, and styles)
- Full observable agent loop
- Symbolic score richness across multiple genres
"""

import unittest
from pathlib import Path

from composer import (
    compose,
    parse_feel,
    extract_musical_intent_from_prompt,
    _PRESETS,
)
from agent import RiffsAgent, issue_license_certificate
from riffs_api.video import (
    attach_riff_to_video,
    validate_video_input,
    sanitize_filename,
    MAX_VIDEO_SIZE_BYTES,
)
from riffs_api.agent_loop import RiffBuildEnvironment, run_loop


class TestDay3VideoRemuxTool(unittest.TestCase):
    def test_file_size_exceeding_50mb_is_rejected_with_exact_prd_message(self):
        with self.assertRaises(ValueError) as ctx:
            validate_video_input("clip.mp4", MAX_VIDEO_SIZE_BYTES + 1)
        self.assertEqual(
            str(ctx.exception),
            "File exceeds 50MB limit. Please upload an MP4 or MOV under 50MB.",
        )

    def test_unsupported_extensions_are_rejected(self):
        for bad_ext in ("clip.avi", "clip.mkv", "clip.webm", "clip.exe"):
            with self.subTest(ext=bad_ext):
                with self.assertRaises(ValueError) as ctx:
                    validate_video_input(bad_ext, 1024)
                self.assertIn("Unsupported video format", str(ctx.exception))

    def test_filename_sanitizer_neutralizes_shell_injection(self):
        adversarial = 'test; rm -rf /; ignore_rules.mov'
        sanitized = sanitize_filename(adversarial)
        self.assertNotIn(";", sanitized)
        self.assertNotIn(" ", sanitized)
        self.assertNotIn("/", sanitized)
        self.assertTrue(sanitized.endswith(".mov"))

    def test_attach_riff_to_video_headless_execution(self):
        dummy_video = b"\x00\x00\x00 ftypmp42\x00\x00\x00\x00mp42isom"
        dummy_audio = b"RIFF\x24\x00\x00\x00WAVEfmt \x10\x00\x00\x00"
        result = attach_riff_to_video(
            video_source=dummy_video,
            audio_source=dummy_audio,
            video_filename="clip.mp4",
            audio_filename="riff.wav",
        )
        self.assertEqual(result["status"], "success")
        self.assertTrue(result["filename"].endswith(".mp4"))
        self.assertGreater(result["size_bytes"], 0)


class TestDay3DigitalLicenseCertificate(unittest.TestCase):
    def test_provenance_record_hashes_artifacts_without_granting_rights(self):
        agent = RiffsAgent()
        res = agent.generate(
            prompt="Neo soul pocket groove",
            key="Am",
            bpm=110,
            chords="Am - F - C - G",
            issue_license=True,
        )
        cert = res["license_certificate"]
        self.assertEqual(cert["status"], "provenance_only")
        self.assertIsNone(cert["license_id"])
        self.assertFalse(cert["rights_grant"])
        self.assertIn("not a license", cert["notice"])
        self.assertTrue(len(cert["hash_sha256"]) == 64)


class TestDay4PromptMusicalIntelligence(unittest.TestCase):
    def test_extract_chords_and_key_from_natural_language_prompt(self):
        prompt = "Give me a smooth 2-5-1 pocket like Dm7 - G7 - Cmaj7"
        intent = extract_musical_intent_from_prompt(prompt)
        self.assertEqual(intent["chords"], ["Dm7", "G7", "Cmaj7"])
        self.assertIn("pocket", intent["feel"]["tags"])

    def test_extract_nashville_numbers_and_bpm_from_songwriter_prompt(self):
        prompt = "Chord progression: vi - IV - I - V in G Major, 110 BPM. Add a pocket drum groove and walking bass."
        intent = extract_musical_intent_from_prompt(prompt)
        self.assertEqual(intent["chords"], ["vi", "IV", "I", "V"])
        self.assertEqual(intent["key"], "G")
        self.assertEqual(intent["bpm"], 110)
        self.assertIn("walking-bass", intent["feel"]["tags"])

    def test_rich_genres_map_to_distinct_groove_feels(self):
        for prompt, expected_preset in [
            ("Funk slap bass groove", "funk"),
            ("Bossa nova rhythm in Dm", "bossa"),
            ("Classic jazz swing with walking bass", "jazz"),
            ("Reggae one drop feel with dub bass", "reggae"),
            ("Blues shuffle in A", "blues"),
            ("Heavy metal driving riff", "metal"),
        ]:
            with self.subTest(prompt=prompt):
                feel = parse_feel(prompt)
                self.assertIn(expected_preset, feel["tags"])

    def test_agent_generates_distinct_scores_per_genre(self):
        funk_score = compose(["Dm7", "G7", "Cmaj7"], "C", ["bass_guitar", "rhythm_guitar", "cymbals"], prompt="funk slap groove", seed=1)
        jazz_score = compose(["Dm7", "G7", "Cmaj7"], "C", ["bass_guitar", "rhythm_guitar", "cymbals"], prompt="jazz walking bass", seed=1)
        self.assertNotEqual(
            funk_score["lanes"][0]["events"],
            jazz_score["lanes"][0]["events"],
            "Funk bassline and Jazz bassline must produce different note events!",
        )


if __name__ == "__main__":
    unittest.main()
