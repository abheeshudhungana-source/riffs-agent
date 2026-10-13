"""Initial symbolic export layer for the render_riff_to_audio tool."""

from __future__ import annotations

import io
import json
import zipfile

from riffs_api.exports import export_symbolic_score, key_filename_slug
from riffs_api.score import draft_score


def render_symbolic_package(progression: str, key: str | None, tempo_bpm: int) -> bytes:
    """Package symbolic exports while an acoustic audio renderer is unselected."""
    score = draft_score(progression, key, tempo_bpm)
    files = export_symbolic_score(score)
    manifest = {
        "tool": "render_riff_to_audio",
        "status": "symbolic_exports_ready",
        "key": score.key,
        "tempo_bpm": score.tempo_bpm,
        "time_signature": score.time_signature,
        "chord_chart": score.chord_chart,
        "nashville_chart": score.nashville_chart,
        "audio_rendered": False,
        "audio_status": "renderer_not_configured",
        "license_certificate": None,
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
