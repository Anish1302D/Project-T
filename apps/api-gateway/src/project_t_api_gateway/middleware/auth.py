"""Header forwarding, secret redaction, and safe logging helpers for API Gateway."""

from __future__ import annotations

import logging
import re

_AUTH_OR_KEY_RE = re.compile(
    r"(Bearer\s+[A-Za-z0-9._\-+/=]+|\bsk-[A-Za-z0-9_-]{8,}|\bAIza[A-Za-z0-9_-]{12,})",
    re.IGNORECASE,
)

_SENSITIVE_HEADER_NAMES = frozenset(
    {
        "authorization",
        "x-api-key",
        "x-goog-api-key",
        "cookie",
        "set-cookie",
    }
)


def redact_gateway_text(text: str) -> str:
    return _AUTH_OR_KEY_RE.sub("[REDACTED]", text)


class GatewayRedactingFilter(logging.Filter):
    """Prevents API keys or Bearer credentials from ever appearing in gateway logs."""

    def filter(self, record: logging.LogRecord) -> bool:
        if isinstance(record.msg, str):
            record.msg = redact_gateway_text(record.msg)
        if isinstance(record.args, tuple):
            record.args = tuple(
                redact_gateway_text(a) if isinstance(a, str) else a for a in record.args
            )
        return True


def build_upstream_headers(
    provider: str,
    incoming_headers: dict[str, str],
    *,
    fallback_api_key: str | None = None,
) -> dict[str, str]:
    """Forward safe protocol headers & credentials to upstream without exposing Project T internals."""
    lowered = {k.lower(): v for k, v in incoming_headers.items()}
    forwarded: dict[str, str] = {"content-type": "application/json"}

    for passthrough_key in ("idempotency-key", "x-request-id", "anthropic-version", "anthropic-beta"):
        if passthrough_key in lowered:
            forwarded[passthrough_key] = lowered[passthrough_key]

    if provider == "openai":
        auth = lowered.get("authorization")
        if auth:
            forwarded["authorization"] = auth
        elif fallback_api_key:
            forwarded["authorization"] = f"Bearer {fallback_api_key}"
    elif provider == "anthropic":
        api_key = lowered.get("x-api-key") or fallback_api_key
        if api_key:
            forwarded["x-api-key"] = api_key
        forwarded.setdefault("anthropic-version", "2023-06-01")
    elif provider == "google":
        goog_key = lowered.get("x-goog-api-key") or fallback_api_key
        if goog_key:
            forwarded["x-goog-api-key"] = goog_key

    return forwarded


def redacted_headers_snapshot(headers: dict[str, str]) -> dict[str, str]:
    """Return header map safe for diagnostic inspection (all secret headers masked)."""
    return {
        k: ("[REDACTED]" if k.lower() in _SENSITIVE_HEADER_NAMES else v)
        for k, v in headers.items()
    }
