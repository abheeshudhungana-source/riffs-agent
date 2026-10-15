"""Least-privilege tool allowlist for the deterministic RIFFs agent loop."""

from __future__ import annotations

from typing import Any, Callable

ALLOWED_TOOLS: dict[str, dict[str, str]] = {
    # These are the only tools used by the current observe/decide/act loop.
    "parse_progression": {"access": "read"},
    "draft_score": {"access": "write"},
    "export_symbolic": {"access": "write"},
}

TOOLS: dict[str, Callable[..., Any]] = {}


def register_tool(name: str, func: Callable[..., Any]) -> None:
    """Register or replace an executable implementation."""
    TOOLS[name] = func


def call_tool(name: str, action: str, *args: Any, **kwargs: Any) -> Any:
    """Execute a tool only when both its name and action are explicitly allowed."""
    permissions = ALLOWED_TOOLS.get(name)
    if permissions is None:
        raise PermissionError(f"Tool '{name}' not allowed")
    if action not in {"read", "write"}:
        raise PermissionError("Action must be 'read' or 'write'")
    if action != permissions["access"]:
        if permissions["access"] == "read" and action == "write":
            raise PermissionError(f"'{name}' is read-only")
        raise PermissionError(f"'{name}' only permits {permissions['access']!r} actions")

    tool_fn = TOOLS.get(name)
    if tool_fn is None:
        raise NotImplementedError(f"Tool '{name}' is allowed but no implementation is registered")
    return tool_fn(action, *args, **kwargs)


def _handle_parse_progression(
    action: str,
    progression: str = "",
    key: str | None = None,
    **kwargs: Any,
) -> dict[str, Any]:
    from dataclasses import asdict
    from riffs_api.progression import parse_progression

    parsed = parse_progression(progression, key)
    return {
        "key": parsed.key,
        "chord_chart": parsed.chord_chart,
        "nashville_chart": parsed.nashville_chart,
        "chords": [asdict(chord) for chord in parsed.chords],
    }


def _handle_draft_score(
    action: str,
    progression: str = "",
    key: str | None = None,
    tempo_bpm: int = 110,
    groove: str | None = None,
    instruments: list[str] | None = None,
    **kwargs: Any,
) -> dict[str, Any]:
    from dataclasses import asdict
    from riffs_api.score import draft_score, draft_instrument_score

    score = draft_score(progression, key, tempo_bpm)
    lanes = {
        instrument: asdict(draft_instrument_score(score, instrument, groove))
        for instrument in (instruments or ["bass_guitar", "rhythm_guitar", "drum_kit"])
    }
    return {**asdict(score), "groove": groove, "parts": lanes}


def _handle_export_symbolic(
    action: str,
    progression: str = "",
    key: str | None = None,
    tempo_bpm: int = 110,
    prompt: str = "",
    groove: str | None = None,
    instruments: list[str] | None = None,
    **kwargs: Any,
) -> dict[str, Any]:
    from io import BytesIO
    from zipfile import ZipFile
    from riffs_api.render import render_symbolic_package, symbolic_package_filename

    archive = render_symbolic_package(
        progression, key, tempo_bpm, prompt=prompt, groove=groove, instruments=instruments,
    )
    with ZipFile(BytesIO(archive)) as package:
        filenames = package.namelist()
    return {
        "filename": symbolic_package_filename(key, tempo_bpm),
        "files": filenames,
        "size_bytes": len(archive),
        "audio_rendered": True,
        "audio_status": "synthetic_preview",
        "license_certificate_issued": False,
        "license_status": "not_issued",
    }


register_tool("parse_progression", _handle_parse_progression)
register_tool("draft_score", _handle_draft_score)
register_tool("export_symbolic", _handle_export_symbolic)
