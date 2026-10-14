"""Initial symbolic export layer for the render_riff_to_audio tool."""

from __future__ import annotations

import io
import json
import hashlib
import zipfile
from dataclasses import replace

from riffs_api.audio import render_preview_wav
from riffs_api.exports import ExportFile, export_symbolic_score, key_filename_slug, midi_bytes
from riffs_api.originality import check_melodic_similarity
from riffs_api.prompt_intent import resolve_groove
from riffs_api.score import SUPPORTED_INSTRUMENTS, draft_instrument_score, draft_score, midi_channel_for_instrument


def render_symbolic_package(
    progression: str,
    key: str | None,
    tempo_bpm: int,
    prompt: str = "",
    groove: str | None = None,
    instruments: list[str] | None = None,
) -> bytes:
    """Package symbolic lanes, a synthetic WAV preview, and provenance metadata."""
    score = draft_score(progression, key, tempo_bpm)
    resolved_groove, groove_source = resolve_groove(prompt, groove)
    selected = instruments or ["bass_guitar", "rhythm_guitar", "drum_kit"]
    unsupported = sorted(set(selected) - set(SUPPORTED_INSTRUMENTS))
    if unsupported:
        raise ValueError(f"Unsupported instrument selection: {', '.join(unsupported)}.")
    lanes = [draft_instrument_score(score, instrument, resolved_groove) for instrument in selected]
    mixed = replace(score, bars=tuple(
        replace(bar, notes=tuple(note for lane in lanes for note in lane.bars[index].notes))
        for index, bar in enumerate(score.bars)
    ))
    key_slug = key_filename_slug(key)
    lane_exports = tuple(
        ExportFile(f"riff_{key_slug}_{tempo_bpm}bpm_{instrument}.mid", "audio/midi", midi_bytes(lane, channel=midi_channel_for_instrument(instrument)))
        for instrument, lane in zip(selected, lanes)
    )
    files = (*export_symbolic_score(score), *lane_exports, ExportFile(
        f"riff_{key_filename_slug(key)}_{tempo_bpm}bpm_preview.wav",
        "audio/wav",
        render_preview_wav(mixed),
    ))
    melody_checks = {
        instrument: check_melodic_similarity({"bars": [
            {"bar": bar.bar, "notes": [note.__dict__ for note in bar.notes]}
            for bar in lane.bars
        ]})
        for instrument, lane in zip(selected, lanes)
        if instrument in {"tenor_sax", "piccolo"}
    }
    provenance_hash = hashlib.sha256(b"".join(file.content for file in files)).hexdigest()
    manifest = {
        "tool": "render_riff_to_audio",
        "status": "preview_ready",
        "key": score.key,
        "tempo_bpm": score.tempo_bpm,
        "time_signature": score.time_signature,
        "chord_chart": score.chord_chart,
        "nashville_chart": score.nashville_chart,
        "audio_rendered": True,
        "audio_status": "synthetic_preview",
        "audio_source": "built-in deterministic oscillator synthesis; no recorded samples",
        "groove": resolved_groove,
        "groove_source": groove_source,
        "instruments": selected,
        "melodic_similarity": melody_checks,
        "license_certificate": {
            "status": "provenance_only",
            "rights_grant": False,
            "sha256": provenance_hash,
            "notice": "This provenance record is not a license or copyright clearance.",
        },
        "files": [file.filename for file in files],
    }

    buffer = io.BytesIO()
    with zipfile.ZipFile(buffer, mode="w", compression=zipfile.ZIP_DEFLATED) as archive:
        archive.writestr("manifest.json", json.dumps(manifest, indent=2))
        for file in files:
            archive.writestr(file.filename, file.content)
    return buffer.getvalue()


def symbolic_package_filename(key: str | None, tempo_bpm: int) -> str:
    return f"riff_{key_filename_slug(key)}_{tempo_bpm}bpm_symbolic.zip"
