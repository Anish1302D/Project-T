"""Core tokenizer adapter protocol and offline generic estimator."""

from __future__ import annotations

import math
import re
from dataclasses import dataclass, field
from typing import Any, Protocol, runtime_checkable

from project_t_contracts import AccuracyLevel, TokenCountResult

_WORD_OR_PUNCT_RE = re.compile(r"\w+|[^\w\s]", re.UNICODE)


@dataclass(frozen=True, slots=True)
class ModelRequest:
    """Normalized model request structure matching Section 8.1."""

    provider: str
    model: str
    messages: list[dict[str, Any]] = field(default_factory=list)
    system: str | None = None
    tools: list[dict[str, Any]] = field(default_factory=list)


@runtime_checkable
class TokenizerAdapter(Protocol):
    """Provider-agnostic token counting interface."""

    provider: str

    def count_text(self, text: str, model: str) -> TokenCountResult:
        """Count or estimate tokens for plain text."""
        ...

    def count_request(self, request: ModelRequest) -> TokenCountResult:
        """Count or estimate tokens for a structured chat/tool request."""
        ...


def estimate_tokens_heuristic(text: str) -> int:
    """
    Conservative offline heuristic token estimator.

    Combines character-length approximation and lexical/punctuation chunking so
    code/JSON punctuation overhead is reflected without claiming exactness.
    """
    if not text:
        return 0
    char_estimate = math.ceil(len(text) / 4)
    pieces = len(_WORD_OR_PUNCT_RE.findall(text))
    lexical_estimate = math.ceil(pieces * 1.15)
    return max(1, round((char_estimate + lexical_estimate) / 2))


def serialize_request_text(request: ModelRequest) -> tuple[str, int]:
    """Flatten request fields and return (serialized_text, structural_overhead_tokens)."""
    import json

    parts: list[str] = []
    overhead = 3  # baseline conversation framing
    if request.system:
        parts.append(request.system)
        overhead += 4
    for msg in request.messages:
        role = str(msg.get("role", ""))
        content = msg.get("content", "")
        if isinstance(content, str):
            parts.append(f"{role}: {content}")
        else:
            parts.append(f"{role}: {json.dumps(content, ensure_ascii=False)}")
        overhead += 4
    if request.tools:
        parts.append(json.dumps(request.tools, ensure_ascii=False))
        overhead += 8 * len(request.tools)
    return "\n".join(parts), overhead


class GenericFallbackTokenizer:
    """Offline fallback estimator; always labels counts as 'estimated'."""

    def __init__(self, provider: str = "local") -> None:
        self.provider = provider

    def count_text(self, text: str, model: str = "generic") -> TokenCountResult:
        return TokenCountResult(
            count=estimate_tokens_heuristic(text),
            accuracy=AccuracyLevel.ESTIMATED,
            model=model,
            provider=self.provider,
        )

    def count_request(self, request: ModelRequest) -> TokenCountResult:
        serialized, overhead = serialize_request_text(request)
        base = estimate_tokens_heuristic(serialized) if serialized else 0
        total = base + overhead if (serialized or request.messages or request.tools) else 0
        return TokenCountResult(
            count=total,
            accuracy=AccuracyLevel.ESTIMATED,
            model=request.model,
            provider=request.provider or self.provider,
        )
