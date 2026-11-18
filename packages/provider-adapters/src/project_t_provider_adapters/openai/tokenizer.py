"""OpenAI tokenizer adapter using local tiktoken encodings with offline fallback."""

from __future__ import annotations

from project_t_contracts import AccuracyLevel, TokenCountResult

from ..interfaces import (
    ModelRequest,
    estimate_tokens_heuristic,
    serialize_request_text,
)

# Authoritative OpenAI model -> tiktoken encoding mapping.
# Unknown or placeholder models intentionally fall back to 'estimated'.
_OPENAI_MODEL_ENCODINGS: dict[str, str] = {
    "gpt-4o": "o200k_base",
    "gpt-4o-mini": "o200k_base",
    "gpt-4.1": "o200k_base",
    "gpt-4.1-mini": "o200k_base",
    "gpt-4.1-nano": "o200k_base",
    "o1": "o200k_base",
    "o3": "o200k_base",
    "o3-mini": "o200k_base",
    "o4-mini": "o200k_base",
    "gpt-4": "cl100k_base",
    "gpt-4-turbo": "cl100k_base",
    "gpt-3.5-turbo": "cl100k_base",
}


class OpenAITokenizerAdapter:
    """Counts tokens using tiktoken for recognized OpenAI models, falling back safely offline."""

    provider: str = "openai"

    def __init__(self, *, allow_tiktoken: bool = True) -> None:
        self._allow_tiktoken = allow_tiktoken
        self._encoding_cache: dict[str, object] = {}

    def _resolve_encoding_name(self, model: str) -> str | None:
        normalized = model.strip().lower()
        if normalized in _OPENAI_MODEL_ENCODINGS:
            return _OPENAI_MODEL_ENCODINGS[normalized]
        for prefix, enc_name in _OPENAI_MODEL_ENCODINGS.items():
            if normalized.startswith(f"{prefix}-"):
                return enc_name
        return None

    def _encode_count(self, text: str, encoding_name: str) -> int | None:
        if not self._allow_tiktoken:
            return None
        try:
            encoding = self._encoding_cache.get(encoding_name)
            if encoding is None:
                import tiktoken  # type: ignore[import-not-found]

                encoding = tiktoken.get_encoding(encoding_name)
                self._encoding_cache[encoding_name] = encoding
            return len(encoding.encode(text, disallowed_special=()))  # type: ignore[attr-defined]
        except Exception:
            return None

    def count_text(self, text: str, model: str) -> TokenCountResult:
        if not text:
            encoding_name = self._resolve_encoding_name(model)
            return TokenCountResult(
                count=0,
                accuracy=AccuracyLevel.EXACT if encoding_name else AccuracyLevel.ESTIMATED,
                model=model,
                provider=self.provider,
            )

        encoding_name = self._resolve_encoding_name(model)
        if encoding_name is not None:
            exact_count = self._encode_count(text, encoding_name)
            if exact_count is not None:
                return TokenCountResult(
                    count=exact_count,
                    accuracy=AccuracyLevel.EXACT,
                    model=model,
                    provider=self.provider,
                )

        return TokenCountResult(
            count=estimate_tokens_heuristic(text),
            accuracy=AccuracyLevel.ESTIMATED,
            model=model,
            provider=self.provider,
        )

    def count_request(self, request: ModelRequest) -> TokenCountResult:
        # Structured request framing varies across endpoints/tool schemas, so local
        # request serialization is always conservatively labeled 'estimated'.
        serialized, overhead = serialize_request_text(request)
        if not serialized and not request.messages and not request.tools:
            return TokenCountResult(
                count=0,
                accuracy=AccuracyLevel.ESTIMATED,
                model=request.model,
                provider=self.provider,
            )

        encoding_name = self._resolve_encoding_name(request.model)
        body_tokens: int | None = None
        if encoding_name is not None:
            body_tokens = self._encode_count(serialized, encoding_name)
        if body_tokens is None:
            body_tokens = estimate_tokens_heuristic(serialized)

        return TokenCountResult(
            count=body_tokens + overhead,
            accuracy=AccuracyLevel.ESTIMATED,
            model=request.model,
            provider=self.provider,
        )
