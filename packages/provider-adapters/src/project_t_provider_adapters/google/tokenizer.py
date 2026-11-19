"""Google Gemini tokenizer adapter with offline estimation and opt-in remote counting."""

from __future__ import annotations

from typing import Any

import httpx
from project_t_contracts import AccuracyLevel, TokenCountResult

from ..interfaces import GenericFallbackTokenizer, ModelRequest

GEMINI_API_BASE = "https://generativelanguage.googleapis.com/v1beta"


class GoogleTokenizerAdapter:
    """
    Token counter for Google Gemini models.

    Local counting is conservatively labeled 'estimated'.
    When allow_remote=True with a valid key, calls Gemini :countTokens and returns 'exact'.
    """

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

    async def count_request_remote(
        self,
        request: ModelRequest,
        *,
        api_key: str,
        http_client: httpx.AsyncClient | None = None,
        api_base: str = GEMINI_API_BASE,
    ) -> TokenCountResult:
        """Opt-in online Gemini :countTokens call with graceful offline fallback."""
        contents: list[dict[str, Any]] = []
        for msg in request.messages:
            role = "model" if msg.get("role") == "assistant" else "user"
            content = msg.get("content", "")
            contents.append({"role": role, "parts": [{"text": str(content)}]})

        body: dict[str, Any] = {"contents": contents or [{"role": "user", "parts": [{"text": ""}]}]}
        if request.system:
            body["systemInstruction"] = {"parts": [{"text": request.system}]}

        url = f"{api_base.rstrip('/')}/models/{request.model}:countTokens"
        try:
            if http_client is not None:
                resp = await http_client.post(
                    url,
                    json=body,
                    headers={"x-goog-api-key": api_key, "content-type": "application/json"},
                    timeout=5.0,
                )
            else:
                async with httpx.AsyncClient(timeout=5.0) as client:
                    resp = await client.post(
                        url,
                        json=body,
                        headers={"x-goog-api-key": api_key, "content-type": "application/json"},
                    )
            if resp.status_code == 200:
                data = resp.json()
                total = data.get("totalTokens")
                if isinstance(total, int) and total >= 0:
                    return TokenCountResult(
                        count=total,
                        accuracy=AccuracyLevel.EXACT,
                        model=request.model,
                        provider=self.provider,
                    )
        except Exception:
            pass

        return self.count_request(request)
