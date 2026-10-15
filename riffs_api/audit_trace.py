"""Redacted audit tracer for RIFFs Human-in-the-Loop vocal checkpoints.

Privacy & Security Guarantees:
- NEVER logs raw lyric text.
- NEVER logs raw HMAC secret or token signatures.
- NEVER logs personal user credentials.
- Records deterministic hashes of request context and lyrics, masked token IDs,
  and structured outcome codes for auditing and compliance.
"""

from __future__ import annotations

import hashlib
import json
import os
import pathlib
import threading
from datetime import datetime, timezone
from typing import Any, Dict, Optional

TRACES_DEFAULT_DIR = pathlib.Path(".riffs_traces")
DEFAULT_TRACE_FILE = TRACES_DEFAULT_DIR / "audit_trace.jsonl"
_LOCK = threading.Lock()


def get_trace_file(custom_trace_file: Optional[pathlib.Path] = None) -> pathlib.Path:
    if custom_trace_file is not None:
        return custom_trace_file
    env_path = os.getenv("RIFFS_AUDIT_LOG_PATH")
    if env_path:
        return pathlib.Path(env_path)
    return DEFAULT_TRACE_FILE


def _mask_token_id(jti_or_token: Optional[str]) -> Optional[str]:
    """Return a non-reversible masked identifier (first 8 chars of SHA-256)."""
    if not jti_or_token:
        return None
    token_str = str(jti_or_token).strip()
    # If it's a full claims.signature token, extract jti if possible or hash the string
    return hashlib.sha256(token_str.encode("utf-8")).hexdigest()[:12]


def record_audit_event(
    event_type: str,
    context_hash: str,
    lyrics_hash: str,
    token_id: Optional[str] = None,
    status: str = "success",
    error_code: Optional[str] = None,
    detail: Optional[str] = None,
    metadata: Optional[Dict[str, Any]] = None,
    custom_trace_file: Optional[pathlib.Path] = None,
) -> Dict[str, Any]:
    """
    Append an immutable, redacted audit record.

    Event types:
      - 'checkpoint_created': Initial draft generated, token issued.
      - 'approval_accepted': Token verified, vocal lead synthesized.
      - 'approval_rejected': Refused (mismatch, expired, replayed, safety, match).
    """
    event = {
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "event_type": event_type,
        "context_sha256": context_hash,
        "lyrics_sha256": lyrics_hash,
        "token_masked_id": _mask_token_id(token_id),
        "status": status,
        "error_code": error_code,
        "detail": detail,
        "metadata": metadata or {},
    }

    target_file = get_trace_file(custom_trace_file)
    try:
        target_file.parent.mkdir(parents=True, exist_ok=True)
        line = json.dumps(event, sort_keys=True, separators=(",", ":")) + "\n"
        with _LOCK:
            with open(target_file, "a", encoding="utf-8") as f:
                f.write(line)
    except Exception:
        # Trace logging must be fail-safe and never crash the primary audio request
        pass

    return event


def read_audit_traces(custom_trace_file: Optional[pathlib.Path] = None) -> list[Dict[str, Any]]:
    """Read parsed audit trace records for tests and operational inspection."""
    target_file = get_trace_file(custom_trace_file)
    if not target_file.exists():
        return []
    with _LOCK:
        records = []
        for line in target_file.read_text(encoding="utf-8").splitlines():
            line = line.strip()
            if line:
                try:
                    records.append(json.loads(line))
                except json.JSONDecodeError:
                    continue
        return records
