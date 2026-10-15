"""Local melodic-contour similarity checks; this is not copyright clearance."""

from __future__ import annotations

import json
import os
from pathlib import Path
from typing import Any


def _intervals(pitches: list[int]) -> tuple[int, ...]:
    return tuple(b - a for a, b in zip(pitches, pitches[1:]))


def _melody_intervals(score: dict[str, Any]) -> tuple[int, ...]:
    events = []
    for bar in score.get("bars", []):
        for note in bar.get("notes", []):
            events.append(((int(bar.get("bar", 1)) - 1) * 4 + float(note["onset_beats"]), int(note["pitch_midi"])))
    events.sort()
    # Collapse repeated notes: the checker compares melodic contour, not rhythm.
    pitches = []
    for _, pitch in events:
        if not pitches or pitches[-1] != pitch:
            pitches.append(pitch)
    return _intervals(pitches)


def _corpus(path: str) -> list[dict[str, Any]]:
    payload = json.loads(Path(path).read_text(encoding="utf-8"))
    if not isinstance(payload, list):
        raise ValueError("Melody corpus must be a JSON array.")
    records = []
    for row in payload:
        if not isinstance(row, dict):
            continue
        pitches = row.get("pitches")
        intervals = row.get("intervals")
        if isinstance(pitches, list) and len(pitches) >= 6:
            intervals = list(_intervals([int(p) for p in pitches]))
        if isinstance(intervals, list) and len(intervals) >= 5:
            records.append({"id": str(row.get("id", "unknown")), "intervals": tuple(int(i) for i in intervals)})
    return records


def check_melodic_similarity(score: dict[str, Any], corpus_path: str | None = None) -> dict[str, Any]:
    """Compare transposition-invariant intervals against an optional licensed local corpus."""
    path = corpus_path or os.getenv("RIFFS_MELODY_CORPUS")
    if not path:
        return {"status": "not_configured", "matches": [], "is_clearance": False}
    try:
        corpus = _corpus(path)
    except (OSError, ValueError, TypeError) as exc:
        return {"status": "corpus_error", "detail": type(exc).__name__, "matches": [], "is_clearance": False}
    candidate = _melody_intervals(score)
    if len(candidate) < 5:
        return {"status": "insufficient_melody", "matches": [], "is_clearance": False}
    matches = []
    for entry in corpus:
        ref = entry["intervals"]
        if len(ref) < 5:
            continue
        # Exact six-note interval windows avoid labeling broad tonal similarity as a match.
        width = 5
        candidate_windows = {candidate[i:i + width] for i in range(len(candidate) - width + 1)}
        if any(ref[i:i + width] in candidate_windows for i in range(len(ref) - width + 1)):
            matches.append(entry["id"])
    return {
        "status": "checked" if not matches else "potential_match",
        "matches": matches,
        "is_clearance": False,
        "method": "exact five-interval contour windows, transposition invariant",
        "corpus": Path(path).name,
    }
