"""Engine-side tokenization protocol and built-in offline generic fallback estimator."""

from __future__ import annotations

import math
import re
from typing import Protocol, runtime_checkable

from project_t_contracts import AccuracyLevel, TokenCountResult

_TOKEN_CHUNK_RE = re.compile(r"\w+|[^\w\s]", re.UNICODE)


@runtime_checkable
class TokenizerProtocol(Protocol):
    """Minimal tokenizer dependency protocol keeping optimization-core provider-independent."""

    provider: str

    def count_text(self, text: str, model: str) -> TokenCountResult:
        ...


def estimate_tokens_offline(text: str) -> int:
    """Deterministic offline token estimate without external dependencies."""
    if not text:
        return 0
    char_estimate = math.ceil(len(text) / 4)
    pieces = len(_TOKEN_CHUNK_RE.findall(text))
    lexical_estimate = math.ceil(pieces * 1.15)
    return max(1, round((char_estimate + lexical_estimate) / 2))


def calculate_savings_percentage(original_tokens: int, optimized_tokens: int) -> float:
    """Compute Savings % per Section 7.8: ((Original - Optimized) / Original) * 100."""
    if original_tokens <= 0:
        return 0.0
    return round(((original_tokens - optimized_tokens) / original_tokens) * 100.0, 2)


class GenericOfflineEstimator:
    """Built-in fallback estimator that always marks results 'estimated'."""

    provider: str = "local"

    def count_text(self, text: str, model: str = "generic") -> TokenCountResult:
        return TokenCountResult(
            count=estimate_tokens_offline(text),
            accuracy=AccuracyLevel.ESTIMATED,
            model=model,
            provider=self.provider,
        )


class TokenEstimator:
    """Counts tokens through an injected TokenizerProtocol with safe offline fallback."""

    def __init__(self, adapter: TokenizerProtocol | None = None) -> None:
        self._fallback = GenericOfflineEstimator()
        self._adapter = adapter if adapter is not None else self._fallback

    def count(self, text: str, model: str = "generic") -> TokenCountResult:
        try:
            return self._adapter.count_text(text, model)
        except Exception:
            return self._fallback.count_text(text, model)
