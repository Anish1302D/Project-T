"""Optional Redis response cache with seamless in-memory fallback when Redis is offline."""

from __future__ import annotations

import json
import time
from typing import Any


class AnalyticsCache:
    """TTL cache backed optionally by Redis, failing open cleanly to local memory."""

    def __init__(self, redis_url: str | None = None, *, default_ttl_seconds: int = 15) -> None:
        self._ttl = default_ttl_seconds
        self._local: dict[str, tuple[float, str]] = {}
        self._redis_client: Any = None
        if redis_url:
            try:
                import redis  # type: ignore[import-not-found]

                client = redis.Redis.from_url(redis_url, decode_responses=True, socket_timeout=0.5)
                client.ping()
                self._redis_client = client
            except Exception:
                self._redis_client = None

    @property
    def backend_name(self) -> str:
        return "redis" if self._redis_client is not None else "memory"

    def get_json(self, key: str) -> dict[str, Any] | None:
        if self._redis_client is not None:
            try:
                raw = self._redis_client.get(key)
                if raw:
                    return json.loads(raw)
            except Exception:
                pass
        entry = self._local.get(key)
        if entry is None:
            return None
        expires_at, payload = entry
        if time.monotonic() > expires_at:
            self._local.pop(key, None)
            return None
        return json.loads(payload)

    def set_json(self, key: str, value: dict[str, Any]) -> None:
        serialized = json.dumps(value)
        if self._redis_client is not None:
            try:
                self._redis_client.setex(key, self._ttl, serialized)
            except Exception:
                pass
        self._local[key] = (time.monotonic() + self._ttl, serialized)

    def invalidate_user(self, user_id: str) -> None:
        prefix = f"analytics:{user_id}:"
        for k in list(self._local.keys()):
            if k.startswith(prefix):
                self._local.pop(k, None)
        if self._redis_client is not None:
            try:
                for k in self._redis_client.scan_iter(match=f"{prefix}*"):
                    self._redis_client.delete(k)
            except Exception:
                pass
