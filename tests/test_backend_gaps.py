import json
import io
import os
import tempfile
import unittest
import wave
from pathlib import Path

from riffs_api.audio import render_preview_wav
from riffs_api.originality import check_melodic_similarity
from riffs_api.prompt_intent import resolve_groove
from riffs_api.score import draft_instrument_score, draft_score
from riffs_api.take_store import get_take, store_take


class BackendGapTests(unittest.TestCase):
    def test_prompt_infers_half_time_shuffle_and_explicit_groove_wins(self):
        self.assertEqual(resolve_groove("halftime shuffle"), ("half_time_shuffle", "prompt"))
        self.assertEqual(resolve_groove("halftime shuffle", "swing"), ("swing", "explicit"))

    def test_synthetic_preview_is_a_valid_wave_file(self):
        score = draft_score("Am - F - C - G", "Am", 110)
        lane = draft_instrument_score(score, "drum_kit", "half_time_shuffle")
        rendered = render_preview_wav(lane)
        self.assertEqual(rendered[:4], b"RIFF")
        with wave.open(io.BytesIO(rendered)) as wav:
            self.assertEqual(wav.getnchannels(), 1)
            self.assertEqual(wav.getsampwidth(), 2)
            self.assertEqual(wav.getframerate(), 22_050)
            self.assertGreater(wav.getnframes(), 0)

    def test_take_store_round_trip(self):
        with tempfile.TemporaryDirectory() as directory:
            previous = os.environ.get("RIFFS_TAKE_STORE_PATH")
            os.environ["RIFFS_TAKE_STORE_PATH"] = directory
            try:
                saved = store_take({"take_id": 7, "score": {"lanes": []}}, owner_id="alice")
                loaded = get_take(saved["storage_id"], owner_id="alice")
                hidden_from_other_owner = get_take(saved["storage_id"], owner_id="bob")
            finally:
                if previous is None:
                    os.environ.pop("RIFFS_TAKE_STORE_PATH", None)
                else:
                    os.environ["RIFFS_TAKE_STORE_PATH"] = previous
        self.assertEqual(loaded["take"]["take_id"], 7)
        self.assertEqual(loaded["storage_id"], saved["storage_id"])
        self.assertEqual(loaded["owner_id"], "alice")
        self.assertIsNone(hidden_from_other_owner)

    def test_take_endpoint_hides_records_from_other_authenticated_users(self):
        from app import get_stored_take

        with tempfile.TemporaryDirectory() as directory:
            previous_path = os.environ.get("RIFFS_TAKE_STORE_PATH")
            os.environ["RIFFS_TAKE_STORE_PATH"] = directory
            try:
                saved = store_take({"take_id": 8}, owner_id="alice")
                alice_response = get_stored_take(saved["storage_id"], user_id="alice")
                self.assertEqual(alice_response["status"], "success")

                bob_response = get_stored_take(saved["storage_id"], user_id="bob")
                self.assertEqual(bob_response.status_code, 404)
            finally:
                if previous_path is None:
                    os.environ.pop("RIFFS_TAKE_STORE_PATH", None)
                else:
                    os.environ["RIFFS_TAKE_STORE_PATH"] = previous_path

    def test_melody_match_is_transposition_invariant_and_not_clearance(self):
        pitches = [60, 62, 65, 64, 67, 69]
        score = {"bars": [{"bar": 1, "notes": [
            {"onset_beats": index * 0.5, "pitch_midi": pitch + 12}
            for index, pitch in enumerate(pitches)
        ]}]}
        with tempfile.TemporaryDirectory() as directory:
            corpus_path = Path(directory) / "melodies.json"
            corpus_path.write_text(json.dumps([{"id": "licensed-example", "pitches": pitches}]), encoding="utf-8")
            result = check_melodic_similarity(score, str(corpus_path))
        self.assertEqual(result["status"], "potential_match")
        self.assertEqual(result["matches"], ["licensed-example"])
        self.assertFalse(result["is_clearance"])


if __name__ == "__main__":
    unittest.main()
