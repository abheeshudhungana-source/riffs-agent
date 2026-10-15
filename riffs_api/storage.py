"""Shared Redis client for distributed rate limits and one-use tokens."""

from __future__ import annotations

import os

_redis_client = None


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
