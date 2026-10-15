"""Small deterministic PCM renderer for symbolic score previews."""

from __future__ import annotations

import io
import math
import wave
from array import array

from riffs_api.score import ScoreDraft


SAMPLE_RATE = 22_050
MAX_RENDER_SECONDS = 120
_TAU = math.tau


def render_preview_wav(score: ScoreDraft) -> bytes:
    """Render a mono 16-bit WAV preview using built-in synthesis (no samples)."""
    seconds_per_beat = 60.0 / score.tempo_bpm
    total_beats = max(
        (bar.bar - 1) * score.beats_per_bar + note.onset_beats + note.duration_beats
        for bar in score.bars
        for note in bar.notes
    )
    duration_seconds = total_beats * seconds_per_beat
    if duration_seconds <= 0 or duration_seconds > MAX_RENDER_SECONDS:
        raise ValueError(f"Audio preview must be between 0 and {MAX_RENDER_SECONDS} seconds.")

    frame_count = math.ceil(duration_seconds * SAMPLE_RATE)
    mix = array("f", [0.0]) * frame_count
    for bar in score.bars:
        bar_start_beats = (bar.bar - 1) * score.beats_per_bar
        for note in bar.notes:
            start = round((bar_start_beats + note.onset_beats) * seconds_per_beat * SAMPLE_RATE)
            length = min(
                frame_count - start,
                max(1, round(note.duration_beats * seconds_per_beat * SAMPLE_RATE)),
            )
            if length <= 0:
                continue
            frequency = 440.0 * (2.0 ** ((note.pitch_midi - 69) / 12.0))
            amplitude = (note.velocity / 127.0) * 0.16
            release_frames = max(1, min(length // 3, round(0.18 * SAMPLE_RATE)))
            phase = 0.0
            for offset in range(length):
                t = offset / SAMPLE_RATE
                if offset < round(0.012 * SAMPLE_RATE):
                    envelope = offset / max(1, round(0.012 * SAMPLE_RATE))
                elif offset >= length - release_frames:
                    envelope = max(0.0, (length - offset) / release_frames)
                else:
                    envelope = math.exp(-1.8 * t)
                phase = _TAU * frequency * t
                tone = (
                    math.sin(phase)
                    + 0.24 * math.sin(phase * 2.0)
                    + 0.08 * math.sin(phase * 3.0)
                )
                mix[start + offset] += amplitude * envelope * tone

    peak = max((abs(value) for value in mix), default=0.0)
    gain = min(1.0, 0.88 / peak) if peak else 1.0
    pcm = array("h", (max(-32768, min(32767, round(value * gain * 32767))) for value in mix))
    if pcm.itemsize != 2:
        raise RuntimeError("This Python runtime does not support 16-bit audio samples.")

    buffer = io.BytesIO()
    with wave.open(buffer, "wb") as output:
        output.setnchannels(1)
        output.setsampwidth(2)
        output.setframerate(SAMPLE_RATE)
        output.writeframes(pcm.tobytes())
    return buffer.getvalue()
