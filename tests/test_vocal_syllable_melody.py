"""Musical and approval-boundary regression tests for syllable-aligned vocals."""
import unittest
from unittest.mock import patch
from agent import _generate_vocal_melody_events, split_syllables, count_syllables
from tests import test_lyrics_vocal_hitl as hitl


class TestSyllableMelody(unittest.TestCase):
    def test_known_words(self):
        for word, count in [('beautiful', 3), ('midnight', 2), ('the', 1), ('rain', 1)]:
            self.assertEqual(count_syllables(word), count)
        self.assertEqual(split_syllables(''), [])

    def test_alignment_harmony_range_and_determinism(self):
        chords = ['Am', 'F', 'C', 'G']
        bars = [{'text': text} for text in ['Beautiful midnight rain', 'Oh', '', 'the rain ' * 12]]
        events = _generate_vocal_melody_events(chords, 'Am', bars, 17)
        self.assertEqual(events, _generate_vocal_melody_events(chords, 'Am', bars, 17))
        self.assertLessEqual(max(e['midi'] for e in events) - min(e['midi'] for e in events), 16)
        tones = [{9, 0, 4}, {5, 9, 0}, {0, 4, 7}, {7, 11, 2}]
        for i, bar in enumerate(bars):
            notes = [e for e in events if e['bar'] == i + 1]
            self.assertEqual(len(notes), count_syllables(bar['text']))
            for note in notes:
                self.assertTrue({'beat', 'dur', 'midi', 'vel', 'lyric', 'syllable', 'vowel',
                                 'onset', 'word', 'word_start', 'melisma', 'phrase_end'} <= note.keys())
                self.assertIn(note['vowel'], {'a', 'e', 'i', 'o', 'u', 'neutral'})
                self.assertGreater(note['dur'], 0)
                self.assertLessEqual(note['beat'] + note['dur'], (i + 1) * 4)
                if note['beat'] % 4 in (0, 2) or note['phrase_end']:
                    self.assertIn(note['midi'] % 12, tones[i])


class TestVocalOriginality(unittest.TestCase):
    def setUp(self):
        self.fixture = hitl.TestLyricsVocalHITL()
        self.fixture.setUp()
        self.addCleanup(self.fixture.tearDown)

    def _checkpoint(self, **kwargs):
        return self.fixture._checkpoint(**kwargs)

    def _approve(self, *args, **kwargs):
        return self.fixture._approve(*args, **kwargs)
    def test_vocal_check_is_reported_and_matches_block(self):
        checkpoint = self._checkpoint()
        approved = self._approve(checkpoint)
        self.assertIn('vocal_lead', approved['melodic_similarity'])
        checkpoint = self._checkpoint(seed=18)
        from riffs_api.originality import check_melodic_similarity
        def check(payload):
            if payload.get('instrument') == 'vocal_lead':
                return {'status': 'potential_match', 'matches': ['test']}
            return check_melodic_similarity(payload)
        with patch('riffs_api.originality.check_melodic_similarity', side_effect=check):
            with self.assertRaisesRegex(Exception, 'possible reference match'):
                self._approve(checkpoint, seed=18)
