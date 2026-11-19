"""Anthropic tokenizer adapter with offline estimation and opt-in online exact counting."""

from __future__ import annotations

from typing import Any

import httpx
from project_t_contracts import AccuracyLevel, TokenCountResult

from ..interfaces import GenericFallbackTokenizer, ModelRequest

ANTHROPIC_COUNT_TOKENS_URL = "https://api.anthropic.com/v1/messages/count_tokens"


class AnthropicTokenizerAdapter:
    """
    Token counter for Anthropic Claude models.

    Local counting is always conservatively labeled 'estimated'.
    When allow_remote=True and an API key is provided, queries Anthropic's
    /v1/messages/count_tokens endpoint and marks exact results as 'exact'.
    """

    provider: str = "anthropic"

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

    async def count_request_remote(
        self,
        request: ModelRequest,
        *,
        api_key: str,
        http_client: httpx.AsyncClient | None = None,
        endpoint: str = ANTHROPIC_COUNT_TOKENS_URL,
    ) -> TokenCountResult:
        """Opt-in online Anthropic exact token counting with graceful offline fallback."""
        body: dict[str, Any] = {
            "model": request.model,
            "messages": request.messages or [{"role": "user", "content": ""}],
        }
        if request.system:
            body["system"] = request.system
        if request.tools:
            body["tools"] = request.tools

        headers = {
            "x-api-key": api_key,
            "anthropic-version": "2023-06-01",
            "content-type": "application/json",
        }
        try:
            if http_client is not None:
                resp = await http_client.post(endpoint, json=body, headers=headers, timeout=5.0)
            else:
                async with httpx.AsyncClient(timeout=5.0) as client:
                    resp = await client.post(endpoint, json=body, headers=headers)
            if resp.status_code == 200:
                data = resp.json()
                input_tokens = data.get("input_tokens")
                if isinstance(input_tokens, int) and input_tokens >= 0:
                    return TokenCountResult(
                        count=input_tokens,
                        accuracy=AccuracyLevel.EXACT,
                        model=request.model,
                        provider=self.provider,
                    )
        except Exception:
            pass

        return self.count_request(request)
