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
    onset_beats: float
    duration_beats: float
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


_PERCUSSION_INSTRUMENTS = {
    "bass_drums", "floor_tom", "bongos", "cymbals", "triangle", "drum_kit",
}
_BASS_INSTRUMENTS = {"bass_guitar", "contrabass"}
_CHORD_INSTRUMENTS = {"rhythm_guitar", "acoustic_piano", "ukulele"}
_PERCUSSION_PITCHES = {
    "bass_drums": (36, 36),       # Bass drum 1
    "floor_tom": (43, 47),       # High and low floor tom
    "bongos": (60, 64),          # Low and high bongo
    "cymbals": (42, 46),         # Closed and open hi-hat
    "triangle": (80, 81),        # Muted and open triangle
}
SUPPORTED_GROOVES = ("straight", "half_time", "swing", "half_time_shuffle")
SUPPORTED_INSTRUMENTS = (
    "bass_guitar", "contrabass", "bass_drums", "floor_tom", "bongos",
    "rhythm_guitar", "acoustic_piano", "tenor_sax", "cymbals", "ukulele",
    "triangle", "piccolo", "drum_kit",
)
_HALF_TIME_GROOVES = {"half_time", "half_time_shuffle"}
_SWING_GROOVES = {"swing", "half_time_shuffle"}


def instrument_role(instrument: str) -> str:
    """Return the deterministic arrangement role for a supported lane."""
    normalized = instrument.strip().lower()
    if normalized in _PERCUSSION_INSTRUMENTS:
        return "percussion"
    if normalized in _BASS_INSTRUMENTS:
        return "bass"
    if normalized in _CHORD_INSTRUMENTS:
        return "chords"
    return "melody"


def midi_channel_for_instrument(instrument: str) -> int:
    """Use General MIDI channel 10 for percussion lanes, channel 1 otherwise."""
    return 9 if instrument_role(instrument) == "percussion" else 0


def draft_instrument_score(
    score: ScoreDraft,
    instrument: str,
    groove: str = "straight",
) -> ScoreDraft:
    """Create a role-specific symbolic lane using a supported rhythmic feel."""
    if groove not in SUPPORTED_GROOVES:
        choices = ", ".join(SUPPORTED_GROOVES)
        raise ValueError(f"Unsupported groove '{groove}'. Choose one of: {choices}.")

    role = instrument_role(instrument)
    bars: list[ScoreBar] = []

    for bar in score.bars:
        chord_tones = [note.pitch_midi for note in bar.notes]
        root = chord_tones[0]

        if groove == "straight" and role == "bass":
            fifth = chord_tones[2] if len(chord_tones) > 2 else root + 7
            shift = -24 if instrument.strip().lower() == "contrabass" else -12
            notes = (
                ScoreNote(root + shift, 0, 2, 92),
                ScoreNote(fifth + shift, 2, 2, 76),
            )
        elif groove in _HALF_TIME_GROOVES and role == "bass":
            fifth = chord_tones[2] if len(chord_tones) > 2 else root + 7
            shift = -24 if instrument.strip().lower() == "contrabass" else -12
            notes = (
                ScoreNote(root + shift, 0, 3, 92),
                ScoreNote(fifth + shift, 3, 1, 72),
            )
        elif groove == "swing" and role == "bass":
            fifth = chord_tones[2] if len(chord_tones) > 2 else root + 7
            shift = -24 if instrument.strip().lower() == "contrabass" else -12
            # A swung eighth-note pickup leads into the fifth on beat 2.
            notes = (
                ScoreNote(root + shift, 0, 2 / 3, 92),
                ScoreNote(fifth + shift, 2 / 3, 4 / 3, 68),
                ScoreNote(root + shift, 2, 2 / 3, 84),
                ScoreNote(fifth + shift, 8 / 3, 4 / 3, 72),
            )
        elif role == "chords":
            octave = 12 if instrument.strip().lower() == "ukulele" else 0
            voicing = tuple(pitch + octave for pitch in chord_tones[:4])
            if groove in _HALF_TIME_GROOVES:
                chord_attacks = ((0, 1, 86), (3, 1, 66))
            elif groove == "swing":
                chord_attacks = ((0, 1 / 3, 86), (2 / 3, 1 / 3, 62), (2, 1 / 3, 76), (8 / 3, 1 / 3, 62))
            else:
                chord_attacks = ((0, 1, 86), (2, 1, 72))
            notes = tuple(
                ScoreNote(pitch, onset, duration, velocity)
                for onset, duration, velocity in chord_attacks
                for pitch in voicing
            )
        elif role == "percussion":
            inst_name = instrument.strip().lower()
            if inst_name == "drum_kit":
                if groove in _HALF_TIME_GROOVES:
                    kit_notes = [
                        ScoreNote(36, 0.0, 1.0, 110),
                        ScoreNote(38, 2.0, 1.0, 106),
                    ]
                    if groove == "half_time_shuffle":
                        for beat in range(4):
                            kit_notes.append(ScoreNote(42, float(beat), 1 / 3, 84))
                            kit_notes.append(ScoreNote(42, beat + 2 / 3, 1 / 3, 68))
                    else:
                        for sub in range(8):
                            kit_notes.append(ScoreNote(42, sub * 0.5, 0.5, 84 if sub % 2 == 0 else 68))
                    notes = tuple(sorted(kit_notes, key=lambda n: (n.onset_beats, n.pitch_midi)))
                elif groove == "swing":
                    kit_notes = [
                        ScoreNote(36, 0.0, 1.0, 108),
                        ScoreNote(38, 1.0, 1.0, 102),
                        ScoreNote(36, 2.0, 1.0, 96),
                        ScoreNote(38, 3.0, 1.0, 102),
                    ]
                    for b in range(4):
                        kit_notes.append(ScoreNote(42, float(b), 1 / 3, 84))
                        kit_notes.append(ScoreNote(42, b + 2 / 3, 1 / 3, 68))
                    notes = tuple(sorted(kit_notes, key=lambda n: (n.onset_beats, n.pitch_midi)))
                else:  # straight
                    kit_notes = [
                        ScoreNote(36, 0.0, 1.0, 108),
                        ScoreNote(38, 1.0, 1.0, 102),
                        ScoreNote(36, 2.0, 1.0, 96),
                        ScoreNote(38, 3.0, 1.0, 102),
                    ]
                    for sub in range(8):
                        kit_notes.append(ScoreNote(42, sub * 0.5, 0.5, 84 if sub % 2 == 0 else 68))
                    notes = tuple(sorted(kit_notes, key=lambda n: (n.onset_beats, n.pitch_midi)))
            else:
                first, second = _PERCUSSION_PITCHES[inst_name]
                if groove in _HALF_TIME_GROOVES:
                    events = ((0, first, 104), (3, second, 76))
                elif inst_name == "bass_drums":
                    events = ((0, first, 108), (2, first, 92))
                elif inst_name == "floor_tom":
                    events = ((0, first, 90), (2, second, 78))
                elif inst_name == "bongos":
                    events = ((0, first, 82), (1, second, 64), (2, first, 76), (3, second, 64))
                elif inst_name == "cymbals":
                    events = ((0, first, 70), (1, first, 54), (2, first, 64), (3, second, 74))
                else:  # triangle
                    events = ((0, first, 55), (1, first, 42), (2, first, 50), (3, second, 62))
                if groove in _SWING_GROOVES:
                    events = tuple((2 / 3 if onset == 1 else 8 / 3 if onset == 3 else onset, pitch, velocity) for onset, pitch, velocity in events)
                notes = tuple(ScoreNote(pitch, onset, 1 / 3 if groove in _SWING_GROOVES else 1, velocity) for onset, pitch, velocity in events)
        else:
            melody_tones = chord_tones[:3] or [root]
            pattern = (0, 1, 2, 1)
            octave = 12 if instrument.strip().lower() in {"piccolo", "tenor_sax"} else 0
            if groove in _HALF_TIME_GROOVES:
                melody_events = ((0, 0, 1.5, 84), (2, 2, 2, 72))
            elif groove in _SWING_GROOVES:
                melody_events = tuple(
                    (beat // 2 + (2 / 3 if beat % 2 else 0), degree, 1 / 3, 84 if beat % 2 == 0 else 68)
                    for beat, degree in enumerate((0, 1, 1, 2, 2, 1, 1, 0))
                )
            else:
                melody_events = tuple(
                    (beat, degree, 1, 84 if beat in (0, 2) else 68)
                    for beat, degree in enumerate(pattern)
                )
            notes = tuple(
                ScoreNote(melody_tones[degree % len(melody_tones)] + octave, onset, duration, velocity)
                for onset, degree, duration, velocity in melody_events
            )

        bars.append(
            ScoreBar(
                bar=bar.bar,
                chord_symbol=bar.chord_symbol,
                nashville=bar.nashville,
                notes=notes,
            )
        )

    return ScoreDraft(
        key=score.key,
        tempo_bpm=score.tempo_bpm,
        time_signature=score.time_signature,
        beats_per_bar=score.beats_per_bar,
        chord_chart=score.chord_chart,
        nashville_chart=score.nashville_chart,
        bars=tuple(bars),
    )


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
