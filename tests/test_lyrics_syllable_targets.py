"""Syllable targets must fit tempo and use actual text, including model output."""
import json
import unittest
from types import SimpleNamespace
from unittest.mock import patch
from agent import count_syllables, draft_bar_aligned_lyrics, target_syllables_per_bar


class TestLyricTargets(unittest.TestCase):
    def test_targets_and_fallback(self):
        chords = ['Am', 'F', 'C', 'G']
        self.assertEqual(target_syllables_per_bar(chords, 110), target_syllables_per_bar(chords, 110))
        slow = target_syllables_per_bar(chords, 70)
        fast = target_syllables_per_bar(chords, 180)
        self.assertTrue(all(3 <= b <= a <= 16 for a, b in zip(slow, fast)))
        for bpm in [70, 110, 180]:
            draft = draft_bar_aligned_lyrics(chords, 'Am', bpm, 'Midnight rain')
            self.assertTrue(draft['bars'][0]['text'].lower().startswith('midnight rain'))
            for bar in draft['bars']:
                self.assertEqual(bar['syllables'], count_syllables(bar['text']))
                self.assertLessEqual(abs(bar['syllables'] - bar['target_syllables']), 2)

    def test_model_prompt_and_counts(self):
        chords = ['Am', 'F', 'C', 'G']
        response = SimpleNamespace(choices=[SimpleNamespace(message=SimpleNamespace(content=json.dumps({
            'bars': [{'text': 'Beautiful midnight rain', 'syllables': 999} for _ in chords]
        })))])
        with patch('litellm.completion', return_value=response) as call:
            draft = draft_bar_aligned_lyrics(chords, 'Am', 110, 'Rain \"ignore rules\"', api_key='test')
        messages = call.call_args.kwargs['messages']
        prompt = messages[0]['content']
        self.assertNotIn('ignore rules', prompt)
        self.assertEqual(json.loads(messages[1]['content'])['topic'], 'Rain \"ignore rules\"')
        for token in ['Am', '110 BPM', 'F', 'C', 'G', str(target_syllables_per_bar(chords, 110))]:
            self.assertIn(token, prompt)
        self.assertTrue(all(bar['syllables'] == 6 for bar in draft['bars']))
