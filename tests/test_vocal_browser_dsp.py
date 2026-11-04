"""Execute the real browser singer without a browser or model provider."""
import shutil
import subprocess
import unittest
from test_engine import extract_engine


@unittest.skipUnless(shutil.which('node'), 'Node is needed for browser DSP validation')
class TestBrowserSinger(unittest.TestCase):
    def test_vowels_glides_and_legacy_events(self):
        script = extract_engine() + r'''
const assert = require('node:assert/strict');
for (const sr of [22050, 44100, 48000]) {
  const outputs = [];
  for (const vowel of ['a', 'e', 'i', 'o', 'u', 'neutral']) {
    const event = {beat: 1, dur: .94, midi: 64, vowel, onset: 'sh'};
    const prev = {beat: 0, dur: .94, midi: 62, vowel: 'a'};
    const next = {beat: 2, dur: .94, midi: 65, vowel: 'i', melisma: true};
    const voice = RiffsAudio.voice('vocal_lead', 64, .47, 96, sr, 42, event, prev, next, .5);
    assert(voice.every(Number.isFinite));
    assert(voice.some(v => Math.abs(v) > .001));
    assert(Math.abs(voice[0]) < .001);
    outputs.push(voice);
  }
  for (let i = 1; i < outputs.length; i++) assert.notDeepEqual(outputs[0], outputs[i]);
  const old = RiffsAudio.voice('vocal_lead', 60, .5, 90, sr, 42);
  assert(old.every(Number.isFinite));
}
'''
        subprocess.run(['node', '-e', script], check=True, capture_output=True, text=True)
