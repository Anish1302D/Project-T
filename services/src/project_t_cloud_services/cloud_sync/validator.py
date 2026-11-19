"""Privacy-boundary validator rejecting raw prompts, source paths, secrets, and unsalted hashes."""

from __future__ import annotations

import re
from typing import Any

# Fields forbidden anywhere in cloud-sync payloads per ADR-0008 and ADR-0011.
FORBIDDEN_SYNC_KEYS: frozenset[str] = frozenset(
    {
        "raw_content",
        "original_content",
        "optimized_content",
        "prompt",
        "prompts",
        "content",
        "messages",
        "source_code",
        "code",
        "terminal_output",
        "stdout",
        "stderr",
        "file_path",
        "file_paths",
        "absolute_path",
        "relative_path",
        "workspace_root",
        "workspace_path",
        "allowed_paths",
        "allowed_paths_json",
        "diff",
        "content_excerpt",
        "block_hash",
        "file_hash",
        "content_hash",
        "simhash_64",
        "workspace_hash",
        "workspace_key_hash",
        "authorization",
        "api_key",
        "secret",
        "cookie",
        "password",
    }
)

_SENSITIVE_VALUE_RE = re.compile(
    r"(Bearer\s+[A-Za-z0-9._\-+/=]{8,}"
    r"|\bsk-[A-Za-z0-9_-]{8,}"
    r"|\bAIza[A-Za-z0-9_-]{12,}"
    r"|-----BEGIN\s+[A-Z ]+PRIVATE KEY-----"
    r"|[A-Za-z]:\\(?:Users|Projects|src|home)\\"
    r"|(?<![A-Za-z0-9])/(?:Users|home|var|etc|opt|srv)/[^\s]+)",
    re.IGNORECASE,
)


class SyncBoundaryViolationError(ValueError):
    """Raised when a cloud-sync payload attempts to transmit disallowed data."""


def _walk_and_validate(node: Any, path: str = "$") -> None:
    if isinstance(node, dict):
        for raw_key, value in node.items():
            key_norm = str(raw_key).strip().lower()
            if key_norm in FORBIDDEN_SYNC_KEYS:
                raise SyncBoundaryViolationError(
                    f"Forbidden sync field '{raw_key}' at {path}.{raw_key}: "
                    "raw content, filesystem paths, secrets, and low-entropy content hashes cannot be synced."
                )
            _walk_and_validate(value, f"{path}.{raw_key}")
    elif isinstance(node, list):
        for idx, item in enumerate(node):
            _walk_and_validate(item, f"{path}[{idx}]")
    elif isinstance(node, str):
        if _SENSITIVE_VALUE_RE.search(node):
            raise SyncBoundaryViolationError(
                f"Disallowed secret token or filesystem path pattern detected at {path}."
            )


def validate_no_sensitive_sync_data(payload: Any) -> None:
    """Validate recursively that a sync request body contains strictly safe metadata."""
    _walk_and_validate(payload)
