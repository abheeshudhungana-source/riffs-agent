"""Secure approval tokens and validation for the human-reviewed vocal lane."""
from __future__ import annotations

import hashlib
import hmac
import json
import logging
import os
import re
import secrets
import threading
import time
from typing import Any

logger = logging.getLogger("riffs.vocal_approval")
VOCAL_TOKEN_TTL_SECONDS = 600
_USED_TOKENS: dict[str, int] = {}
_TOKEN_LOCK = threading.Lock()
_SUPPORTED_LANGUAGES = {"en", "es", "fr", "ja"}
_SUPPORTED_STYLES = {"soulful_lead"}
_HTML_TAG = re.compile(r"<\s*/?\s*[a-zA-Z][^>]*>")
_DIRECT_VIOLENCE = re.compile(r"\b(?:kill them all|kill you all|murder them all)\b", re.IGNORECASE)


class VocalApprovalError(PermissionError):
    """An invalid, expired, replayed, or mismatched approval token."""


class VocalInputError(ValueError):
    """Invalid vocal settings or lyric content."""

class VocalApprovalUnavailable(RuntimeError):
    """The server has not configured the secret required for approval tokens."""


def validate_vocal_options(language: str, style: str) -> None:
    if language not in _SUPPORTED_LANGUAGES:
        raise VocalInputError(f"Unsupported lyrics language '{language}'.")
    if style not in _SUPPORTED_STYLES:
        raise VocalInputError(f"Unsupported vocal style '{style}'.")


def normalize_lyrics(value: Any, chords: list[str]) -> list[dict[str, Any]]:
    if not isinstance(value, list) or len(value) != len(chords) or not value or len(value) > 16:
        raise VocalInputError("Lyrics must contain exactly one non-empty bar per chord (up to 16 bars).")
    normalized = []
    total = 0
    for index, item in enumerate(value):
        if isinstance(item, str):
            text = item
        elif isinstance(item, dict):
            text = item.get("text", item.get("lyric"))
        else:
            raise VocalInputError("Each lyric bar must be text or an object with a text field.")
        if not isinstance(text, str) or not text.strip():
            raise VocalInputError("Each lyric bar must contain non-empty text.")
        text = text.strip()
        if len(text) > 180:
            raise VocalInputError("Each lyric bar must be 180 characters or fewer.")
        if _HTML_TAG.search(text):
            raise VocalInputError("Lyrics cannot contain HTML or script markup.")
        if _DIRECT_VIOLENCE.search(text):
            raise VocalInputError("Lyrics cannot contain direct violent threats or calls to violence.")
        total += len(text)
        normalized.append({"bar": index + 1, "chord": chords[index % len(chords)], "text": text})
    if total > 2000:
        raise VocalInputError("Lyrics must be 2,000 characters or fewer.")
    return normalized


def _fingerprint(value: Any) -> str:
    encoded = json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode("utf-8")
    return hashlib.sha256(encoded).hexdigest()


def emit_vocal_trace(event: str, context: dict[str, Any], **fields: Any) -> None:
    """Write structured, redacted lifecycle data suitable for app-platform logs."""
    record = {
        "event": event,
        "trace_id": context.get("trace_id"),
        "context_sha256": _fingerprint(context),
        **fields,
    }
    logger.info("riffs_vocal_trace %s", json.dumps(record, sort_keys=True, separators=(",", ":")))

def _secret() -> bytes:
    value = os.getenv("RIFFS_VOCAL_SECRET", "")
    if len(value.encode("utf-8")) < 32:
        raise VocalApprovalUnavailable("Vocal approval is unavailable on this server.")
    return value.encode("utf-8")


def _payload(context: dict[str, Any], lyrics: list[dict[str, Any]], expires: int, nonce: str) -> bytes:
    data = {"context": context, "lyrics": lyrics, "expires": expires, "nonce": nonce}
    return json.dumps(data, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode("utf-8")


def issue_vocal_token(context: dict[str, Any], lyrics: list[dict[str, Any]]) -> str:
    expires = int(time.time()) + VOCAL_TOKEN_TTL_SECONDS
    nonce = secrets.token_urlsafe(18)
    sig = hmac.new(_secret(), _payload(context, lyrics, expires, nonce), hashlib.sha256).hexdigest()
    token = f"{expires}:{nonce}:{sig}"
    emit_vocal_trace(
        "checkpoint_issued", context,
        draft_sha256=_fingerprint(lyrics),
        token_id=hashlib.sha256(token.encode("utf-8")).hexdigest()[:16],
        expires_at=expires,
    )
    return token


def consume_vocal_token(token: str | None, context: dict[str, Any], lyrics: list[dict[str, Any]]) -> bool:
    token_id = hashlib.sha256(token.encode("utf-8")).hexdigest()[:16] if isinstance(token, str) else None
    if not token:
        emit_vocal_trace("approval_rejected", context, reason="missing_token")
        return False
    try:
        expires_raw, nonce, sig = token.split(":", 2)
        expires = int(expires_raw)
    except (AttributeError, TypeError, ValueError):
        emit_vocal_trace("approval_rejected", context, reason="malformed_token", token_id=token_id)
        return False
    if expires < time.time():
        emit_vocal_trace("approval_rejected", context, reason="expired", token_id=token_id, expires_at=expires)
        return False
    expected = hmac.new(_secret(), _payload(context, lyrics, expires, nonce), hashlib.sha256).hexdigest()
    if not hmac.compare_digest(sig, expected):
        emit_vocal_trace(
            "approval_rejected", context, reason="context_or_draft_mismatch",
            token_id=token_id, draft_sha256=_fingerprint(lyrics),
        )
        return False
    with _TOKEN_LOCK:
        for used_token, used_expiry in list(_USED_TOKENS.items()):
            if used_expiry < time.time():
                del _USED_TOKENS[used_token]
        if token in _USED_TOKENS:
            emit_vocal_trace("approval_rejected", context, reason="replay", token_id=token_id)
            return False
        _USED_TOKENS[token] = expires
    emit_vocal_trace(
        "approval_accepted", context,
        token_id=token_id, draft_sha256=_fingerprint(lyrics),
    )
    return True
