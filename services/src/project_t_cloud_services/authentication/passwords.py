"""Salted PBKDF2-HMAC-SHA256 password hashing helpers."""

from __future__ import annotations

import base64
import hashlib
import hmac
import secrets

_PBKDF2_ITERATIONS = 200_000


def hash_password(password: str) -> str:
    """Hash a user password with a fresh 16-byte CSPRNG salt."""
    if len(password) < 8:
        raise ValueError("Password must be at least 8 characters.")
    salt = secrets.token_bytes(16)
    digest = hashlib.pbkdf2_hmac("sha256", password.encode("utf-8"), salt, _PBKDF2_ITERATIONS)
    salt_b64 = base64.b64encode(salt).decode("ascii")
    hash_b64 = base64.b64encode(digest).decode("ascii")
    return f"pbkdf2_sha256${_PBKDF2_ITERATIONS}${salt_b64}${hash_b64}"


def verify_password(password: str, stored_hash: str) -> bool:
    """Verify a plaintext password in constant time."""
    try:
        scheme, iter_str, salt_b64, hash_b64 = stored_hash.split("$", 3)
        if scheme != "pbkdf2_sha256":
            return False
        iterations = int(iter_str)
        salt = base64.b64decode(salt_b64.encode("ascii"))
        expected = base64.b64decode(hash_b64.encode("ascii"))
    except Exception:
        return False

    candidate = hashlib.pbkdf2_hmac("sha256", password.encode("utf-8"), salt, iterations)
    return hmac.compare_digest(candidate, expected)
