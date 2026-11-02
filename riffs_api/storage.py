"""Shared Redis client for distributed rate limits and one-use tokens."""

from __future__ import annotations

import os

_redis_client = None


def public_demo_enabled() -> bool:
    """True only for an explicitly enabled demo with both real signing secrets."""
    enabled = os.getenv("RIFFS_PUBLIC_DEMO", "").strip().lower() in {"1", "true", "yes"}
    jwt_secret = os.getenv("RIFFS_JWT_SECRET", "")
    vocal_secret = os.getenv("RIFFS_VOCAL_SECRET", "")
    return enabled and len(jwt_secret.encode("utf-8")) >= 32 and len(vocal_secret.encode("utf-8")) >= 32


def get_redis():
    global _redis_client
    if _redis_client is None:
        redis_url = os.getenv("REDIS_URL")
        if not redis_url:
            raise RuntimeError("REDIS_URL is not configured")
        from redis import Redis

        _redis_client = Redis.from_url(
            redis_url,
            socket_connect_timeout=2,
            socket_timeout=2,
            decode_responses=True,
        )
    return _redis_client
