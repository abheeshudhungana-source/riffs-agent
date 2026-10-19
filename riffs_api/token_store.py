"""Single-use token store for the vocal approval checkpoint.

Replay protection must be shared by every serverless instance. An in-process
set or a local file only protects one container, so production uses a
Redis-compatible REST store (Vercel KV / Upstash) with atomic
``SET key value EXAT <expiry> NX``. Memory storage is for local development
and tests only; on Vercel without KV configured, the factory fails closed.
"""

from __future__ import annotations

import json
import os
import threading
import time
import urllib.request
from typing import Any, Callable, Optional

KEY_PREFIX = "riffs:vocal:token:"


class TokenStoreUnavailable(RuntimeError):
    """The replay store is missing or unreachable; approvals must not proceed."""


class MemoryTokenStore:
    """Thread-safe single-process store. NOT safe across serverless instances."""

    shared_across_instances = False

    def __init__(self) -> None:
        self._used: dict[str, float] = {}
        self._lock = threading.Lock()

    def consume_token(self, token_id: str, expires_at: float) -> bool:
        now = time.time()
        with self._lock:
            self._used = {k: v for k, v in self._used.items() if v > now}
            if token_id in self._used:
                return False
            self._used[token_id] = float(expires_at)
            return True


class UpstashRedisTokenStore:
    """Atomic once-only consumption over the Upstash/Vercel KV REST API."""

    shared_across_instances = True

    def __init__(
        self,
        url: str,
        token: str,
        post: Optional[Callable[[list[Any]], Any]] = None,
        timeout: float = 3.0,
    ) -> None:
        self._url = url.rstrip("/")
        self._token = token
        self._timeout = timeout
        self._post = post or self._http_post

    def _http_post(self, command: list[Any]) -> Any:
        request = urllib.request.Request(
            self._url,
            data=json.dumps(command).encode("utf-8"),
            headers={"Authorization": f"Bearer {self._token}", "Content-Type": "application/json"},
            method="POST",
        )
        with urllib.request.urlopen(request, timeout=self._timeout) as response:  # noqa: S310
            return json.loads(response.read().decode("utf-8"))

    def consume_token(self, token_id: str, expires_at: float) -> bool:
        # Keep the key slightly past token expiry so clock skew cannot reopen a replay window.
        exat = int(expires_at) + 60
        try:
            body = self._post(["SET", KEY_PREFIX + token_id, "consumed", "EXAT", exat, "NX"])
        except Exception as exc:  # network/auth failure: fail closed
            raise TokenStoreUnavailable(f"Token replay store unreachable: {type(exc).__name__}") from exc
        if not isinstance(body, dict) or "error" in body:
            raise TokenStoreUnavailable("Token replay store returned an error.")
        # "OK" => newly set (first use). null => key already existed (replay).
        return body.get("result") == "OK"


_override: Optional[Any] = None
_memory_store = MemoryTokenStore()


def _is_deployed_environment() -> bool:
    return bool(
        os.getenv("VERCEL")
        or os.getenv("VERCEL_ENV")
        or os.getenv("AWS_LAMBDA_FUNCTION_NAME")
        or os.getenv("ENVIRONMENT", "").lower() == "production"
    )


def _has_serverless_fallback() -> bool:
    return bool(
        os.getenv("RIFFS_ALLOW_SERVERLESS_FALLBACK", "").strip().lower() in {"1", "true", "yes"}
        or os.getenv("VERCEL_URL")
        or os.getenv("VERCEL_REGION")
    )


def set_token_store(store: Optional[Any]) -> None:
    """Install a store explicitly (tests); pass None to restore environment selection."""
    global _override
    _override = store


def get_token_store() -> Any:
    if _override is not None:
        return _override
    url = os.getenv("KV_REST_API_URL") or os.getenv("UPSTASH_REDIS_REST_URL")
    token = os.getenv("KV_REST_API_TOKEN") or os.getenv("UPSTASH_REDIS_REST_TOKEN")
    if url and token:
        return UpstashRedisTokenStore(url, token)
    if _is_deployed_environment() and not _has_serverless_fallback():
        raise TokenStoreUnavailable(
            "Vocal approval needs a shared token store in production: set KV_REST_API_URL and "
            "KV_REST_API_TOKEN (Vercel KV / Upstash). In-memory storage cannot prevent replay "
            "across serverless instances."
        )
    return _memory_store

