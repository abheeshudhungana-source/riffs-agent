import base64
import unittest

from agent import _part_score_payload
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


if __name__ == "__main__":
    unittest.main()
