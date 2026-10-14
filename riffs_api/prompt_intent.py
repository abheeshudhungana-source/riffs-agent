"""Deterministic arrangement intent extraction for the backend API."""

from __future__ import annotations

import re

from riffs_api.score import SUPPORTED_GROOVES


_HALF_TIME = re.compile(r"\b(?:half[\s-]?time|halftime)\b", re.IGNORECASE)
_SWING = re.compile(r"\b(?:swing|swung|triplet feel|shuffle|shuffling)\b", re.IGNORECASE)
_STRAIGHT = re.compile(r"\b(?:straight|no swing|even eighths)\b", re.IGNORECASE)


def resolve_groove(prompt: str = "", requested: str | None = None) -> tuple[str, str]:
    """Return (groove, source); explicit non-default choices override prompt inference."""
    if requested is not None:
        groove = requested.strip().lower().replace("-", "_").replace(" ", "_")
        if groove not in SUPPORTED_GROOVES:
            options = ", ".join(SUPPORTED_GROOVES)
            raise ValueError(f"Unsupported groove '{requested}'. Choose one of: {options}.")
        if groove != "straight":
            return groove, "explicit"

    text = prompt or ""
    if _HALF_TIME.search(text) and _SWING.search(text):
        return "half_time_shuffle", "prompt"
    if _HALF_TIME.search(text):
        return "half_time", "prompt"
    if _STRAIGHT.search(text):
        return "straight", "prompt"
    if _SWING.search(text):
        return "swing", "prompt"
    if requested == "straight":
        return "straight", "explicit"
    return "straight", "default"
