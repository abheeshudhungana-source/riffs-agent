"""Chord progression parsing for the first RIFFs backend slice."""

from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Literal


class ProgressionError(ValueError):
    """Raised when a progression or key cannot be parsed."""


@dataclass(frozen=True)
class ParsedChord:
    bar: int
    source: str
    root: str
    pitch_class: int
    quality: str
    symbol: str
    scale_degree: int | None
    nashville: str | None
    source_kind: Literal["chord_symbol", "nashville", "roman_numeral"]


@dataclass(frozen=True)
class ParsedProgression:
    key: str | None
    chords: tuple[ParsedChord, ...]
    chord_chart: str
    nashville_chart: str | None


_PITCH_CLASSES = {
    "C": 0,
    "C#": 1,
    "DB": 1,
    "D": 2,
    "D#": 3,
    "EB": 3,
    "E": 4,
    "F": 5,
    "F#": 6,
    "GB": 6,
    "G": 7,
    "G#": 8,
    "AB": 8,
    "A": 9,
    "A#": 10,
    "BB": 10,
    "B": 11,
}

_SHARP_NAMES = ("C", "C#", "D", "D#", "E", "F", "F#", "G", "G#", "A", "A#", "B")
_FLAT_NAMES = ("C", "Db", "D", "Eb", "E", "F", "Gb", "G", "Ab", "A", "Bb", "B")
_MAJOR_SCALE = (0, 2, 4, 5, 7, 9, 11)
_MINOR_SCALE = (0, 2, 3, 5, 7, 8, 10)
_MAJOR_QUALITIES = ("major", "minor", "minor", "major", "major", "minor", "diminished")
_MINOR_QUALITIES = ("minor", "diminished", "major", "minor", "minor", "major", "major")
_ROMAN_DEGREES = {"I": 1, "II": 2, "III": 3, "IV": 4, "V": 5, "VI": 6, "VII": 7}

_KEY_RE = re.compile(r"^([A-Ga-g])([#b]?)(?:\s+(major|minor|maj|min|m))?$", re.IGNORECASE)
_CHORD_RE = re.compile(
    r"^(?P<root>[A-Ga-g])(?P<accidental>[#b]?)(?P<quality>minor7|maj7|m7b5|m7|ø|dim7|maj|minor|min|m|dim|°|aug|\+|sus2|sus4|sus|7|6|9|11|13)?$",
    re.IGNORECASE,
)
_NASHVILLE_RE = re.compile(r"^(?P<accidental>[b#]?)(?P<degree>[1-7])(?P<quality>maj7|m7b5|ø|dim7|maj|min|minor|m|dim|°|aug|\+|sus2|sus4|sus|7|6|9|11|13)?$", re.IGNORECASE)
_ROMAN_RE = re.compile(r"^(?P<accidental>[b#]?)(?P<degree>VII|VI|IV|V|III|II|I)(?P<quality>maj7|m7b5|ø|dim7|maj|min|minor|m|dim|°|aug|\+|sus2|sus4|sus|7|6|9|11|13)?$", re.IGNORECASE)


def _normalize_key(key: str | None) -> tuple[str, int, bool] | None:
    if key is None:
        return None
    match = _KEY_RE.fullmatch(key.strip())
    if not match:
        raise ProgressionError(f"Unsupported key '{key}'. Use a key such as 'G major' or 'E minor'.")

    root_text = (match.group(1) + match.group(2)).upper()
    pitch_class = _PITCH_CLASSES.get(root_text)
    if pitch_class is None:
        raise ProgressionError(f"Unsupported key root '{root_text}'.")

    mode_text = (match.group(3) or "major").lower()
    minor = mode_text in {"minor", "min", "m"}
    root_display = _display_pitch(pitch_class, prefer_flats=match.group(2).lower() == "b")
    return f"{root_display} {'minor' if minor else 'major'}", pitch_class, minor


def _display_pitch(pitch_class: int, prefer_flats: bool) -> str:
    names = _FLAT_NAMES if prefer_flats else _SHARP_NAMES
    return names[pitch_class % 12]


def _quality_from_suffix(suffix: str | None, default: str) -> str:
    value = (suffix or "").lower()
    if not value:
        return default
    if value in {"m", "min", "minor"}:
        return "minor"
    if value in {"m7", "minor7"}:
        return "minor7"
    if value in {"dim", "°", "dim7", "ø", "m7b5"}:
        return "half_diminished" if value in {"ø", "m7b5"} else "diminished"
    if value in {"aug", "+"}:
        return "augmented"
    if value in {"sus", "sus2", "sus4"}:
        return value
    if value == "7":
        return "dominant7"
    if value == "maj7":
        return "major7"
    if value in {"6", "9", "11", "13"}:
        return f"major{value}"
    if value in {"maj", "major"}:
        return "major"
    return "major"


def _quality_suffix(quality: str) -> str:
    return {
        "major": "",
        "minor": "m",
        "minor7": "m7",
        "diminished": "dim",
        "half_diminished": "m7b5",
        "augmented": "aug",
        "sus": "sus",
        "sus2": "sus2",
        "sus4": "sus4",
        "dominant7": "7",
        "major7": "maj7",
        "major6": "6",
        "major9": "9",
        "major11": "11",
        "major13": "13",
    }[quality]


def _tokenize(progression: str) -> list[str]:
    tokens = [token.strip() for token in re.split(r"\s*(?:-|–|—|\||,)\s*", progression.strip()) if token.strip()]
    if not tokens:
        raise ProgressionError("Enter at least one chord or Nashville number.")
    if len(tokens) > 32:
        raise ProgressionError("A progression can contain at most 32 bars.")
    return tokens


def _apply_accidental(pitch_class: int, accidental: str) -> int:
    if accidental == "b":
        return (pitch_class - 1) % 12
    if accidental == "#":
        return (pitch_class + 1) % 12
    return pitch_class


def _degree_pitch(tonic: int, minor_key: bool, degree: int, accidental: str) -> int:
    scale = _MINOR_SCALE if minor_key else _MAJOR_SCALE
    return _apply_accidental((tonic + scale[degree - 1]) % 12, accidental)


def _degree_quality(minor_key: bool, degree: int) -> str:
    qualities = _MINOR_QUALITIES if minor_key else _MAJOR_QUALITIES
    return qualities[degree - 1]


def _nashville_label(degree: int, quality: str, accidental: str) -> str:
    quality_suffix = {
        "major": "",
        "minor": "m",
        "minor7": "m7",
        "diminished": "dim",
        "half_diminished": "m7b5",
        "augmented": "aug",
        "sus": "sus",
        "sus2": "sus2",
        "sus4": "sus4",
        "dominant7": "7",
        "major7": "maj7",
        "major6": "6",
        "major9": "9",
        "major11": "11",
        "major13": "13",
    }[quality]
    return f"{accidental}{degree}{quality_suffix}"


def parse_progression(progression: str, key: str | None = None) -> ParsedProgression:
    normalized_key = _normalize_key(key)
    tokens = _tokenize(progression)
    chords: list[ParsedChord] = []

    for bar, token in enumerate(tokens, start=1):
        match = _CHORD_RE.fullmatch(token)
        if match:
            source_root = match.group("root").upper() + match.group("accidental")
            root_pc = _PITCH_CLASSES.get(source_root.upper())
            if root_pc is None:
                raise ProgressionError(f"Unsupported chord root '{source_root}' in bar {bar}.")

            suffix = match.group("quality")
            quality = _quality_from_suffix(suffix, "major")
            root = _display_pitch(root_pc, prefer_flats="b" in source_root.lower())
            degree: int | None = None
            nashville: str | None = None
            if normalized_key:
                _, tonic, minor_key = normalized_key
                intervals = _MINOR_SCALE if minor_key else _MAJOR_SCALE
                for index, interval in enumerate(intervals, start=1):
                    if (tonic + interval) % 12 == root_pc:
                        degree = index
                        break
                if degree is None:
                    for index, interval in enumerate(intervals, start=1):
                        distance = (root_pc - (tonic + interval)) % 12
                        if distance in {1, 11}:
                            degree = index
                            accidental = "#" if distance == 1 else "b"
                            break
                if degree is not None:
                    accidental = "" if (tonic + intervals[degree - 1]) % 12 == root_pc else accidental
                    nashville = _nashville_label(degree, quality, accidental)

            chords.append(ParsedChord(
                bar=bar,
                source=token,
                root=root,
                pitch_class=root_pc,
                quality=quality,
                symbol=f"{root}{_quality_suffix(quality)}",
                scale_degree=degree,
                nashville=nashville,
                source_kind="chord_symbol",
            ))
            continue

        number_match = _NASHVILLE_RE.fullmatch(token)
        roman_match = _ROMAN_RE.fullmatch(token)
        match = number_match or roman_match
        if not match:
            raise ProgressionError(f"Unsupported chord token '{token}' in bar {bar}.")
        if normalized_key is None:
            raise ProgressionError(f"A key is required to resolve Nashville token '{token}' in bar {bar}.")

        _, tonic, minor_key = normalized_key
        accidental = match.group("accidental").lower()
        degree_text = match.group("degree")
        roman = bool(roman_match)
        degree = _ROMAN_DEGREES[degree_text.upper()] if roman else int(degree_text)

        default_quality = _degree_quality(minor_key, degree)
        if roman:
            default_quality = "minor" if degree_text.islower() else "major"
            if degree_text.upper() == "VII" and degree_text.islower():
                default_quality = "diminished"

        suffix = match.group("quality")
        quality = _quality_from_suffix(suffix, default_quality)
        root_pc = _degree_pitch(tonic, minor_key, degree, accidental)
        prefer_flats = "b" in accidental or (normalized_key and "b" in normalized_key[0])
        root = _display_pitch(root_pc, prefer_flats=bool(prefer_flats))
        chords.append(ParsedChord(
            bar=bar,
            source=token,
            root=root,
            pitch_class=root_pc,
            quality=quality,
            symbol=f"{root}{_quality_suffix(quality)}",
            scale_degree=degree,
            nashville=_nashville_label(degree, quality, accidental),
            source_kind="roman_numeral" if roman else "nashville",
        ))

    chord_chart = "| " + " | ".join(chord.symbol for chord in chords) + " |"
    nashville_chart = None
    if all(chord.nashville is not None for chord in chords):
        nashville_chart = "| " + " | ".join(chord.nashville or "" for chord in chords) + " |"

    return ParsedProgression(
        key=normalized_key[0] if normalized_key else None,
        chords=tuple(chords),
        chord_chart=chord_chart,
        nashville_chart=nashville_chart,
    )
