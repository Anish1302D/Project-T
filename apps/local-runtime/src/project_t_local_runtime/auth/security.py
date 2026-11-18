"""Request security guards: bearer auth, Host/Origin validation, rate limits, and redaction."""

from __future__ import annotations

import logging
import re
import secrets
import threading
import time
from collections import deque

_BEARER_RE = re.compile(r"Bearer\s+[A-Za-z0-9._\-+/=]+", re.IGNORECASE)
_API_KEY_RE = re.compile(r"\b(sk-[A-Za-z0-9_-]{8,}|AIza[A-Za-z0-9_-]{12,})\b")


def redact_sensitive_text(text: str) -> str:
    """Scrub bearer tokens and API key strings before emitting diagnostic text or logs."""
    redacted = _BEARER_RE.sub("Bearer [REDACTED]", text)
    return _API_KEY_RE.sub("[REDACTED_KEY]", redacted)


class SecretRedactingFilter(logging.Filter):
    """Logging filter preventing bearer tokens or provider keys from entering log output."""

    def filter(self, record: logging.LogRecord) -> bool:
        if isinstance(record.msg, str):
            record.msg = redact_sensitive_text(record.msg)
        if record.args:
            if isinstance(record.args, tuple):
                record.args = tuple(
                    redact_sensitive_text(a) if isinstance(a, str) else a
                    for a in record.args
                )
            elif isinstance(record.args, dict):
                record.args = {
                    k: redact_sensitive_text(v) if isinstance(v, str) else v
                    for k, v in record.args.items()
                }
        return True


def verify_bearer_token(authorization_header: str | None, expected_token: str) -> bool:
    """Constant-time bearer token check."""
    if not authorization_header:
        return False
    parts = authorization_header.split(" ", 1)
    if len(parts) != 2 or parts[0].lower() != "bearer":
        return False
    presented = parts[1].strip()
    if not presented:
        return False
    return secrets.compare_digest(presented, expected_token)


def is_allowed_host(host_header: str | None, allowed_hosts: frozenset[str]) -> bool:
    """Reject unknown Host headers to prevent DNS rebinding against localhost."""
    if not host_header:
        return False
    return host_header.strip().lower() in allowed_hosts


def is_allowed_origin(origin_header: str | None, allowed_origins: tuple[str, ...]) -> bool:
    """
    Validate Origin header if present.

    Requests without an Origin header (CLI, VS Code extension host, local Python/Node)
    are allowed provided Host and Bearer checks pass; browser/webview origins must match
    the explicit non-wildcard allowlist.
    """
    if origin_header is None:
        return True
    normalized = origin_header.strip().rstrip("/")
    if not normalized:
        return False
    return any(normalized == allowed.strip().rstrip("/") for allowed in allowed_origins if allowed != "*")


class SlidingWindowRateLimiter:
    """Thread-safe local sliding-window rate limiter."""

    def __init__(self, *, max_requests: int, window_seconds: int) -> None:
        self._max_requests = max(1, max_requests)
        self._window_seconds = max(1, window_seconds)
        self._timestamps: deque[float] = deque()
        self._lock = threading.Lock()

    def allow_request(self) -> bool:
        now = time.monotonic()
        cutoff = now - self._window_seconds
        with self._lock:
            while self._timestamps and self._timestamps[0] < cutoff:
                self._timestamps.popleft()
            if len(self._timestamps) >= self._max_requests:
                return False
            self._timestamps.append(now)
            return True
