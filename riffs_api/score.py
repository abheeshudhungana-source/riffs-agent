"""Deterministic symbolic score draft from a parsed chord progression."""

from __future__ import annotations

from dataclasses import dataclass

from riffs_api.progression import ParsedProgression, parse_progression


_CHORD_INTERVALS = {
    "major": (0, 4, 7),
    "minor": (0, 3, 7),
    "minor7": (0, 3, 7, 10),
    "diminished": (0, 3, 6),
    "half_diminished": (0, 3, 6, 10),
    "augmented": (0, 4, 8),
    "sus": (0, 5, 7),
    "sus2": (0, 2, 7),
    "sus4": (0, 5, 7),
    "dominant7": (0, 4, 7, 10),
    "major7": (0, 4, 7, 11),
    "major6": (0, 4, 7, 9),
    "major9": (0, 4, 7, 14),
    "major11": (0, 4, 7, 17),
    "major13": (0, 4, 7, 21),
}


@dataclass(frozen=True)
class ScoreNote:
    pitch_midi: int
    onset_beats: int
    duration_beats: int
    velocity: int


@dataclass(frozen=True)
class ScoreBar:
    bar: int
    chord_symbol: str
    nashville: str | None
    notes: tuple[ScoreNote, ...]


@dataclass(frozen=True)
class ScoreDraft:
    key: str | None
    tempo_bpm: int
    time_signature: str
    beats_per_bar: int
    chord_chart: str
    nashville_chart: str | None
    bars: tuple[ScoreBar, ...]


def draft_score(progression: str, key: str | None, tempo_bpm: int) -> ScoreDraft:
    """Create a plain 4/4 block-chord score as a first symbolic baseline."""
    parsed: ParsedProgression = parse_progression(progression, key)
    beats_per_bar = 4
    bars: list[ScoreBar] = []

    for chord in parsed.chords:
        intervals = _CHORD_INTERVALS[chord.quality]
        root_midi = 60 + chord.pitch_class  # C4 is MIDI note 60.
        notes = tuple(
            ScoreNote(
                pitch_midi=root_midi + interval,
                onset_beats=0,
                duration_beats=beats_per_bar,
                velocity=80,
            )
            for interval in intervals
        )
        bars.append(ScoreBar(
            bar=chord.bar,
            chord_symbol=chord.symbol,
            nashville=chord.nashville,
            notes=notes,
        ))

    return ScoreDraft(
        key=parsed.key,
        tempo_bpm=tempo_bpm,
        time_signature="4/4",
        beats_per_bar=beats_per_bar,
        chord_chart=parsed.chord_chart,
        nashville_chart=parsed.nashville_chart,
        bars=tuple(bars),
    )
