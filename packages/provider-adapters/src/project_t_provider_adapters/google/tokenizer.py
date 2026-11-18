"""Google Gemini offline estimation adapter (remote counting adapter added in Phase 8)."""

from __future__ import annotations

from project_t_contracts import AccuracyLevel, TokenCountResult

from ..interfaces import GenericFallbackTokenizer, ModelRequest


class GoogleTokenizerAdapter:
    """Local offline estimator for Gemini models; strictly marks counts as 'estimated'."""

    provider: str = "google"

    def __init__(self) -> None:
        self._fallback = GenericFallbackTokenizer(provider=self.provider)

    def count_text(self, text: str, model: str) -> TokenCountResult:
        res = self._fallback.count_text(text, model=model)
        return TokenCountResult(
            count=res.count,
            accuracy=AccuracyLevel.ESTIMATED,
            model=model,
            provider=self.provider,
        )

    def count_request(self, request: ModelRequest) -> TokenCountResult:
        return self._fallback.count_request(
            ModelRequest(
                provider=self.provider,
                model=request.model,
                messages=request.messages,
                system=request.system,
                tools=request.tools,
            )
        )
