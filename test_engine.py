"""DSP checks for the in-page audio engine, run headlessly through JavaScriptCore.

The engine lives inline in index.html (Vercel only bundles index.html). This test
extracts it, runs it in `jsc`, and checks that every instrument produces finite,
audible, correctly pitched audio and that a whole loop renders quickly enough.
Skipped when `jsc` is not installed (macOS ships it with JavaScriptCore).
"""

import json
import os
import re
import shutil
import subprocess
import tempfile
import unittest

from composer import compose, INSTRUMENT_TIER

ROOT = os.path.dirname(os.path.abspath(__file__))
JSC_CANDIDATES = [
    os.environ.get("JSC_PATH", ""),
    shutil.which("jsc") or "",
    "/System/Library/Frameworks/JavaScriptCore.framework/Versions/A/Helpers/jsc",
]
JSC = next((p for p in JSC_CANDIDATES if p and os.path.exists(p)), None)

HARNESS = r"""
var SR = 44100;
function stats(buf) {
  var peak = 0, sum = 0, bad = 0;
  for (var i = 0; i < buf.length; i++) {
    var v = buf[i];
    if (!isFinite(v)) { bad++; continue; }
    if (Math.abs(v) > peak) peak = Math.abs(v);
    sum += v * v;
  }
  return { len: buf.length, peak: peak, rms: Math.sqrt(sum / Math.max(1, buf.length)), bad: bad };
}
// Autocorrelation pitch estimate (Hz) of buf[start .. start+win], searching +-12% around `guess`.
function pitch(buf, start, win, guess) {
  var lo = Math.floor(SR / (guess * 1.12)), hi = Math.ceil(SR / (guess * 0.89)), best = -1e9, bestLag = lo, scores = {};
  for (var lag = lo - 1; lag <= hi + 1; lag++) {
    var s = 0;
    for (var i = 0; i < win; i++) s += buf[start + i] * buf[start + i + lag];
    scores[lag] = s;
    if (lag >= lo && lag <= hi && s > best) { best = s; bestLag = lag; }
  }
  var a = scores[bestLag - 1], b = scores[bestLag], c = scores[bestLag + 1];
  var shift = 0.5 * (a - c) / (a - 2 * b + c);
  return SR / (bestLag + shift);
}
var out = { voices: {}, pitch: {}, loop: {}, timing: {} };
var PITCHED = { bass_guitar: 45, contrabass: 40, rhythm_guitar: 57, ukulele: 69, acoustic_piano: 60, tenor_sax: 62, piccolo: 84 };
Object.keys(PITCHED).forEach(function (inst) {
  var midi = PITCHED[inst], v = RiffsAudio.voice(inst, midi, 1.0, 100, SR, 12345);
  out.voices[inst] = stats(v);
  var est = pitch(v, Math.floor(0.2 * SR), 6000, RiffsAudio.mtof(midi));
  out.pitch[inst] = 1200 * Math.log(est / RiffsAudio.mtof(midi)) / Math.LN2;
});
[['bass_drums', 36], ['floor_tom', 41], ['bongos', 60], ['bongos', 61], ['triangle', 81], ['triangle', 80],
 ['cymbals', 42], ['cymbals', 46], ['cymbals', 49], ['cymbals', 51]].forEach(function (p) {
  out.voices[p[0] + ':' + p[1]] = stats(RiffsAudio.voice(p[0], p[1], 0.5, 100, SR, 777));
});
// Velocity is applied when notes are mixed into the loop: harder notes must be louder.
function oneNote(vel) {
  return { loop_bars: 1, beats_per_bar: 4, lanes: [{ tier: 'mid', instrument: 'rhythm_guitar', events: [{ beat: 0, dur: 1, midi: 57, vel: vel }] }] };
}
var soft = stats(RiffsAudio.renderLoop(oneNote(40), 110, SR).tiers.mid), hard = stats(RiffsAudio.renderLoop(oneNote(120), 110, SR).tiers.mid);
out.velocity = { soft: soft.rms, hard: hard.rms };
var a = RiffsAudio.voice('tenor_sax', 62, 0.4, 90, SR, 9), b = RiffsAudio.voice('tenor_sax', 62, 0.4, 90, SR, 9), same = true;
for (var i = 0; i < a.length; i++) if (a[i] !== b[i]) { same = false; break; }
out.reproducible = same;

[44100, 48000].forEach(function (sr) {
  var t0 = Date.now(), loop = RiffsAudio.renderLoop(SCORE, 110, sr), ms = Date.now() - t0;
  out.timing[sr] = ms;
  if (sr === 44100) {
    Object.keys(loop.tiers).forEach(function (tier) { out.loop[tier] = stats(loop.tiers[tier]); });
    out.loop.click = stats(loop.click);
    out.loop.loopSamples = loop.loopSamples;
    var mix = RiffsAudio.mixdown(loop, {}, 2);
    out.loop.mix = stats(mix.left);
    out.loop.mixLen = mix.left.length;
    var muted = RiffsAudio.mixdown(loop, { low: true, mid: true, high: true }, 1);
    out.loop.allMuted = stats(muted.left);
    var wav = RiffsAudio.encodeWav(mix);
    out.wav = { bytes: wav.length, head: String.fromCharCode(wav[0], wav[1], wav[2], wav[3]), sr: wav[24] | (wav[25] << 8) | (wav[26] << 16) };
    var countIn = RiffsAudio.renderCountIn(120, sr, 4);
    out.countIn = stats(countIn);
    // Notes sit where the score says: the bass downbeat of bar 1 is audible at sample 0.
    var bassStart = 0;
    for (var s = 0; s < 4000; s++) bassStart = Math.max(bassStart, Math.abs(loop.tiers.low[s]));
    out.bassOnset = bassStart;
  }
});
// Loudness balance: every instrument playing the same progression should land in a similar RMS range.
out.balance = {};
Object.keys(SCORES).forEach(function (inst) {
  var loop = RiffsAudio.renderLoop(SCORES[inst], 110, SR), tier = Object.keys(loop.tiers)[0];
  out.balance[inst] = stats(loop.tiers[tier]);
});
print(JSON.stringify(out));
"""


def extract_engine():
    with open(os.path.join(ROOT, "index.html"), encoding="utf-8") as handle:
        html = handle.read()
    match = re.search(r'<script id="riffs-engine">(.*?)</script>', html, re.S)
    assert match, "engine script block not found in index.html"
    return match.group(1)


@unittest.skipUnless(JSC, "jsc (JavaScriptCore shell) not available")
class TestAudioEngine(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        score = compose(["Am", "F", "C", "G"], "Am", ["bass_guitar", "rhythm_guitar", "cymbals"], prompt="Neo-Soul", seed=1)
        scores = {inst: compose(["Am", "F", "C", "G"], "Am", [inst], prompt="Neo-Soul", seed=1) for inst in INSTRUMENT_TIER}
        script = (extract_engine() + "\nvar SCORE = " + json.dumps(score) + ";\nvar SCORES = " + json.dumps(scores) + ";\n" + HARNESS)
        with tempfile.NamedTemporaryFile("w", suffix=".js", delete=False) as handle:
            handle.write(script)
            path = handle.name
        try:
            proc = subprocess.run([JSC, path], capture_output=True, text=True, timeout=300)
        finally:
            os.unlink(path)
        assert proc.returncode == 0, proc.stdout + proc.stderr
        cls.out = json.loads(proc.stdout.strip().splitlines()[-1])

    def test_instruments_are_balanced_in_loudness(self):
        rms = {inst: st["rms"] for inst, st in self.out["balance"].items()}
        for inst, value in rms.items():
            self.assertGreater(value, 0.01, inst + " is too quiet")
        self.assertLess(max(rms.values()) / min(rms.values()), 4.5, rms)

    def test_every_voice_is_finite_audible_and_not_clipping(self):
        for name, st in self.out["voices"].items():
            self.assertEqual(st["bad"], 0, name)
            self.assertGreater(st["rms"], 0.005, name + " is silent")
            self.assertLess(st["peak"], 3.0, name + " is wildly loud")

    def test_pitched_voices_are_in_tune(self):
        for name, cents in self.out["pitch"].items():
            self.assertLess(abs(cents), 35, "%s is %.1f cents off" % (name, cents))

    def test_velocity_changes_level_and_voices_are_reproducible(self):
        self.assertGreater(self.out["velocity"]["hard"], self.out["velocity"]["soft"] * 1.5)
        self.assertTrue(self.out["reproducible"])

    def test_loop_has_all_three_tiers_and_a_click(self):
        for tier in ("low", "mid", "high", "click"):
            self.assertGreater(self.out["loop"][tier]["rms"], 0.005, tier)
            self.assertEqual(self.out["loop"][tier]["bad"], 0, tier)
        self.assertGreater(self.out["bassOnset"], 0.01)  # bass note lands on beat 1 of bar 1

    def test_mixdown_is_normalised_and_loop_length_matches_tempo(self):
        beats = 8 * 4
        self.assertEqual(self.out["loop"]["loopSamples"], round(beats * 60 / 110 * 44100))
        self.assertEqual(self.out["loop"]["mixLen"], 2 * self.out["loop"]["loopSamples"])
        self.assertAlmostEqual(self.out["loop"]["mix"]["peak"], 0.85, places=2)
        self.assertEqual(self.out["loop"]["allMuted"]["peak"], 0)

    def test_wav_export_header(self):
        self.assertEqual(self.out["wav"]["head"], "RIFF")
        self.assertEqual(self.out["wav"]["sr"], 44100)
        self.assertEqual(self.out["wav"]["bytes"], 44 + 4 * self.out["loop"]["mixLen"])

    def test_count_in_clicks(self):
        self.assertGreater(self.out["countIn"]["peak"], 0.3)

    def test_render_speed(self):
        for sr, ms in self.out["timing"].items():
            self.assertLess(ms, 4000, "rendering a loop at %s Hz took %d ms" % (sr, ms))


if __name__ == "__main__":
    unittest.main()
