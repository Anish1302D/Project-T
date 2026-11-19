"""JWT access and installation-pairing token helpers."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from typing import Any

import jwt


@dataclass(frozen=True, slots=True)
class AuthenticatedPrincipal:
    """Decoded cloud user or installation sync principal."""

    user_id: str
    email: str
    token_scope: str  # "user" | "sync"
    installation_id: str | None = None
    device_id: str | None = None


def issue_user_token(
    *,
    secret: str,
    user_id: str,
    email: str,
    ttl_seconds: int = 86_400,
) -> str:
    now = datetime.now(tz=UTC)
    payload = {
        "sub": user_id,
        "email": email,
        "scope": "user",
        "iat": int(now.timestamp()),
        "exp": int((now + timedelta(seconds=ttl_seconds)).timestamp()),
    }
    return str(jwt.encode(payload, secret, algorithm="HS256"))


def issue_sync_token(
    *,
    secret: str,
    user_id: str,
    email: str,
    installation_id: str,
    device_id: str,
    ttl_seconds: int = 86_400 * 30,
) -> str:
    now = datetime.now(tz=UTC)
    payload = {
        "sub": user_id,
        "email": email,
        "scope": "sync",
        "installation_id": installation_id,
        "device_id": device_id,
        "iat": int(now.timestamp()),
        "exp": int((now + timedelta(seconds=ttl_seconds)).timestamp()),
    }
    return str(jwt.encode(payload, secret, algorithm="HS256"))


def decode_bearer_token(secret: str, token: str) -> AuthenticatedPrincipal | None:
    try:
        claims: dict[str, Any] = jwt.decode(token, secret, algorithms=["HS256"])
    except jwt.PyJWTError:
        return None
    sub = claims.get("sub")
    email = claims.get("email")
    scope = claims.get("scope", "user")
    if not isinstance(sub, str) or not isinstance(email, str) or scope not in {"user", "sync"}:
        return None
    return AuthenticatedPrincipal(
        user_id=sub,
        email=email,
        token_scope=scope,
        installation_id=claims.get("installation_id") if isinstance(claims.get("installation_id"), str) else None,
        device_id=claims.get("device_id") if isinstance(claims.get("device_id"), str) else None,
    )
