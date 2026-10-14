import unittest
from riffs_api.score import (
    ScoreDraft,
    draft_score,
    draft_instrument_score,
    instrument_role,
    midi_channel_for_instrument,
)
from agent import RiffsAgent


class DrumKitEvalTests(unittest.TestCase):
    def setUp(self):
        self.score = draft_score("C - G - Am - F", "C major", 100)

    def test_drum_kit_role_and_channel(self):
        """drum_kit must be recognized as percussion on General MIDI Channel 10 (idx 9)."""
        self.assertEqual(instrument_role("drum_kit"), "percussion")
        self.assertEqual(midi_channel_for_instrument("drum_kit"), 9)

    def test_straight_groove_kick_snare_hihat_polyphony(self):
        """Straight groove: Kick on 0 & 2, Snare on 1 & 3, Closed Hat on all 8ths."""
        lane = draft_instrument_score(self.score, "drum_kit", "straight")
        bar0 = lane.bars[0].notes

        kicks = [n for n in bar0 if n.pitch_midi == 36]
        snares = [n for n in bar0 if n.pitch_midi == 38]
        hats = [n for n in bar0 if n.pitch_midi == 42]

        # Kick onsets on downbeat pulses (beats 0.0 and 2.0)
        kick_onsets = [n.onset_beats for n in kicks]
        self.assertEqual(kick_onsets, [0.0, 2.0])

        # Snare onsets on backbeats (beats 1.0 and 3.0)
        snare_onsets = [n.onset_beats for n in snares]
        self.assertEqual(snare_onsets, [1.0, 3.0])

        # Closed hi-hat on all 8th notes (8 onsets in 4/4)
        hat_onsets = [n.onset_beats for n in hats]
        self.assertEqual(hat_onsets, [0.0, 0.5, 1.0, 1.5, 2.0, 2.5, 3.0, 3.5])

        # Polyphony check: simultaneous onsets
        # Beat 0.0 must have both Kick and Hat
        onsets_at_0 = {n.pitch_midi for n in bar0 if n.onset_beats == 0.0}
        self.assertIn(36, onsets_at_0)
        self.assertIn(42, onsets_at_0)

        # Beat 1.0 must have both Snare and Hat
        onsets_at_1 = {n.pitch_midi for n in bar0 if n.onset_beats == 1.0}
        self.assertIn(38, onsets_at_1)
        self.assertIn(42, onsets_at_1)

    def test_half_time_groove_shifts_backbeat_to_beat_three(self):
        """Half-time groove: Kick on 0, Snare on 2.0 (musical beat 3), Hats driving 8ths."""
        lane = draft_instrument_score(self.score, "drum_kit", "half_time")
        bar0 = lane.bars[0].notes

        kicks = [n for n in bar0 if n.pitch_midi == 36]
        snares = [n for n in bar0 if n.pitch_midi == 38]

        # Kick on beat 0.0
        kick_onsets = [n.onset_beats for n in kicks]
        self.assertEqual(kick_onsets, [0.0])

        # Half-time backbeat: Snare on beat 2.0 only
        snare_onsets = [n.onset_beats for n in snares]
        self.assertEqual(snare_onsets, [2.0])

        # Polyphony at beat 2.0: Snare and Hat simultaneously
        onsets_at_2 = {n.pitch_midi for n in bar0 if n.onset_beats == 2.0}
        self.assertIn(38, onsets_at_2)
        self.assertIn(42, onsets_at_2)

    def test_swing_groove_subdivisions_with_floating_point_tolerance(self):
        """Swing groove: hats use triplet swing (onset at beat + 2/3), evaluated with tolerance."""
        lane = draft_instrument_score(self.score, "drum_kit", "swing")
        bar0 = lane.bars[0].notes

        hats = [n for n in bar0 if n.pitch_midi == 42]
        hat_onsets = [n.onset_beats for n in hats]

        # For each beat b in 0..3, there should be an onset at b and at b + 2/3
        for b in range(4):
            # Downbeat onset at b
            self.assertTrue(
                any(abs(onset - b) < 0.01 for onset in hat_onsets),
                f"Missing downbeat hat onset at beat {b}",
            )
            # Triplet swing partial at b + 2/3
            swung_partial = b + (2.0 / 3.0)
            self.assertTrue(
                any(abs(onset - swung_partial) < 0.01 for onset in hat_onsets),
                f"Missing swung hat onset at beat {swung_partial} (tolerance 0.01)",
            )

        # Kick on 0.0 and 2.0, Snare on 1.0 and 3.0
        kicks = [n.onset_beats for n in bar0 if n.pitch_midi == 36]
        snares = [n.onset_beats for n in bar0 if n.pitch_midi == 38]
        self.assertEqual(kicks, [0.0, 2.0])
        self.assertEqual(snares, [1.0, 3.0])

    def test_part_locking_preserves_drum_kit(self):
        """Locking drum_kit reuses exact note vectors and hash across chord/key changes."""
        agent = RiffsAgent()
        take1 = agent.generate(
            prompt="straight groove",
            key="C major",
            bpm=100,
            chords="C - G - Am - F",
            instruments=["bass_guitar", "rhythm_guitar", "drum_kit"],
            groove="straight",
        )
        self.assertIn("drum_kit", take1["part_scores"])
        drum_part1 = take1["part_scores"]["drum_kit"]

        # Take 2 changes chords and key, but locks drum_kit
        take2 = agent.generate(
            prompt="jazz reharmonization",
            key="D minor",
            bpm=100,
            chords="Dm - G7 - Cmaj7 - A7",
            instruments=["bass_guitar", "rhythm_guitar", "drum_kit"],
            locked_parts=["drum_kit"],
            base_take_id=take1["take_id"],
            groove="straight",
        )

        drum_part2 = take2["part_scores"]["drum_kit"]
        self.assertTrue(drum_part2["locked"])
        self.assertEqual(drum_part2["note_vector_sha256"], drum_part1["note_vector_sha256"])
        self.assertEqual(drum_part2["bars"], drum_part1["bars"])


if __name__ == "__main__":
    unittest.main()
