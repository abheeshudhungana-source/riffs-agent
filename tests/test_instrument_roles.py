import base64
import hashlib
import unittest

from agent import RiffsAgent, _part_score_payload
from riffs_api.score import (
    draft_instrument_score,
    draft_score,
    instrument_role,
    midi_channel_for_instrument,
)


class InstrumentRoleTests(unittest.TestCase):
    def setUp(self):
        self.score = draft_score("I - IV - V - vi", "C major", 100)

    def test_bass_plays_root_and_fifth_in_low_register(self):
        lane = draft_instrument_score(self.score, "bass_guitar")

        self.assertEqual([(note.onset_beats, note.duration_beats) for note in lane.bars[0].notes], [(0, 2), (2, 2)])
        self.assertEqual([note.pitch_midi for note in lane.bars[0].notes], [48, 55])

    def test_chordal_and_melodic_lanes_have_distinct_rhythms(self):
        chords = draft_instrument_score(self.score, "rhythm_guitar").bars[0].notes
        melody = draft_instrument_score(self.score, "tenor_sax").bars[0].notes

        self.assertEqual([note.onset_beats for note in chords], [0, 0, 0, 2, 2, 2])
        self.assertEqual([note.onset_beats for note in melody], [0, 1, 2, 3])
        self.assertEqual(melody[0].pitch_midi, 72)

    def test_percussion_uses_general_midi_notes_and_channel_ten(self):
        payload = _part_score_payload("cymbals", self.score)
        lane = draft_instrument_score(self.score, "cymbals")
        encoded = base64.b64decode(payload["midi_base64"])

        self.assertEqual(payload["role"], "percussion")
        self.assertEqual(midi_channel_for_instrument("cymbals"), 9)
        self.assertEqual([note.pitch_midi for note in lane.bars[0].notes], [42, 42, 42, 46])
        self.assertIn(bytes((0x99, 42, 70)), encoded)
        self.assertNotIn(bytes((0x90, 42, 70)), encoded)

    def test_stem_and_score_report_the_lane_role(self):
        self.assertEqual(instrument_role("contrabass"), "bass")
        self.assertEqual(instrument_role("acoustic_piano"), "chords")
        self.assertEqual(instrument_role("piccolo"), "melody")

    def test_groove_presets_change_role_specific_timing(self):
        straight_bass = draft_instrument_score(self.score, "bass_guitar", "straight").bars[0].notes
        half_time_bass = draft_instrument_score(self.score, "bass_guitar", "half_time").bars[0].notes
        swing_bass = draft_instrument_score(self.score, "bass_guitar", "swing").bars[0].notes
        swing_chords = draft_instrument_score(self.score, "rhythm_guitar", "swing").bars[0].notes
        half_time_melody = draft_instrument_score(self.score, "tenor_sax", "half_time").bars[0].notes
        swing_percussion = draft_instrument_score(self.score, "cymbals", "swing").bars[0].notes

        self.assertEqual([note.onset_beats for note in straight_bass], [0, 2])
        self.assertEqual([note.onset_beats for note in half_time_bass], [0, 3])
        self.assertEqual([note.onset_beats for note in swing_bass], [0, 2 / 3, 2, 8 / 3])
        self.assertEqual(sorted({note.onset_beats for note in swing_chords}), [0, 2 / 3, 2, 8 / 3])
        self.assertEqual([note.onset_beats for note in half_time_melody], [0, 2])
        self.assertEqual([note.onset_beats for note in swing_percussion], [0, 2 / 3, 2, 8 / 3])

    def test_swing_lane_serializes_triplet_timing_to_midi(self):
        payload = _part_score_payload("tenor_sax", self.score, "swing")
        notes = payload["bars"][0]["notes"]
        encoded = base64.b64decode(payload["midi_base64"])

        self.assertEqual(payload["groove"], "swing")
        self.assertEqual(
            [round(note["onset_beats"] * 3) for note in notes],
            [0, 2, 3, 5, 6, 8, 9, 11],
        )
        self.assertTrue(encoded.startswith(b"MThd"))
        self.assertEqual(payload["midi_sha256"], hashlib.sha256(encoded).hexdigest())

    def test_locked_lane_keeps_its_prior_groove_and_notes(self):
        agent = RiffsAgent()
        first = agent.generate(
            prompt="straight groove",
            key="C major",
            bpm=100,
            chords="I - IV - V - vi",
            instruments=["bass_guitar", "rhythm_guitar"],
            groove="straight",
        )
        second = agent.generate(
            prompt="swing groove",
            key="C major",
            bpm=100,
            chords="I - IV - V - vi",
            instruments=["bass_guitar", "rhythm_guitar"],
            locked_parts=["bass_guitar"],
            base_take_id=first["take_id"],
            groove="swing",
        )

        self.assertEqual(second["groove"], "swing")
        self.assertEqual(second["part_scores"]["bass_guitar"]["groove"], "straight")
        self.assertEqual(
            second["part_scores"]["bass_guitar"]["bars"],
            first["part_scores"]["bass_guitar"]["bars"],
        )
        self.assertEqual(second["part_scores"]["rhythm_guitar"]["groove"], "swing")
        self.assertNotEqual(
            second["part_scores"]["rhythm_guitar"]["bars"],
            first["part_scores"]["rhythm_guitar"]["bars"],
        )

    def test_unknown_groove_is_rejected(self):
        with self.assertRaisesRegex(ValueError, "Unsupported groove"):
            draft_instrument_score(self.score, "bass_guitar", "shuffle-ish")


if __name__ == "__main__":
    unittest.main()
