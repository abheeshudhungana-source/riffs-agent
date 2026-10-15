"""Local JSON take archive for persistent, inspectable generated takes."""

from __future__ import annotations

import json
import os
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


import tempfile


def take_store_directory() -> Path:
    configured = os.getenv("RIFFS_TAKE_STORE_PATH")
    if configured:
        p = Path(configured).expanduser()
        p.mkdir(parents=True, exist_ok=True)
        return p
    if (
        os.getenv("VERCEL")
        or os.getenv("VERCEL_ENV")
        or os.getenv("AWS_LAMBDA_FUNCTION_NAME")
        or os.getenv("ENVIRONMENT", "").lower() == "production"
    ):
        tmp_target = Path(tempfile.gettempdir()) / "riffs_takes"
        tmp_target.mkdir(parents=True, exist_ok=True)
        return tmp_target
    try:
        candidate = Path.home() / ".riffs-agent" / "takes"
        candidate.mkdir(parents=True, exist_ok=True)
        return candidate
    except (PermissionError, OSError):
        pass
    try:
        fallback = Path(__file__).resolve().parent.parent / ".riffs_takes"
        fallback.mkdir(parents=True, exist_ok=True)
        return fallback
    except (PermissionError, OSError):
        tmp_fallback = Path(tempfile.gettempdir()) / "riffs_takes"
        tmp_fallback.mkdir(parents=True, exist_ok=True)
        return tmp_fallback


def store_take(take: dict[str, Any], owner_id: str) -> dict[str, Any]:
    """Write an immutable take record owned by one authenticated principal."""
    if not isinstance(owner_id, str) or not owner_id.strip():
        raise ValueError("owner_id is required to store a take")
    storage_id = str(uuid.uuid4())
    created_at = datetime.now(timezone.utc).isoformat()
    directory = take_store_directory()
    directory.mkdir(parents=True, exist_ok=True)
    record = {"storage_id": storage_id, "owner_id": owner_id, "created_at": created_at, "take": take}
    destination = directory / f"{storage_id}.json"
    temporary = directory / f".{storage_id}.tmp"
    temporary.write_text(json.dumps(record, indent=2, sort_keys=True), encoding="utf-8")
    temporary.replace(destination)
    return {
        "status": "stored",
        "storage_id": storage_id,
        "created_at": created_at,
        "scope": "local_filesystem",
    }


def get_take(storage_id: str, owner_id: str) -> dict[str, Any] | None:
    """Load a take only when its recorded owner matches the authenticated principal."""
    if not isinstance(owner_id, str) or not owner_id.strip():
        return None
    try:
        normalized = str(uuid.UUID(storage_id))
    except (ValueError, TypeError, AttributeError):
        return None
    path = take_store_directory() / f"{normalized}.json"
    if not path.is_file():
        return None
    record = json.loads(path.read_text(encoding="utf-8"))
    if record.get("owner_id") != owner_id:
        return None
    return record
