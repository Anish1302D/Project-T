"""Transparent SSE streaming pass-through with asynchronous usage sniffing."""

from __future__ import annotations

import json
from collections.abc import AsyncIterator, Awaitable, Callable

import httpx
from project_t_provider_adapters import (
    extract_anthropic_usage,
    extract_google_usage,
    extract_openai_usage,
)


def parse_sse_usage_event(provider: str, payload: dict) -> tuple[int | None, int | None]:
    """Extract (input_tokens, cached_input_tokens) from a parsed SSE JSON event."""
    if provider == "openai":
        return extract_openai_usage(payload)
    if provider == "anthropic":
        return extract_anthropic_usage(payload)
    if provider == "google":
        return extract_google_usage(payload)
    return None, None


async def stream_upstream_sse(
    *,
    client: httpx.AsyncClient,
    upstream_url: str,
    headers: dict[str, str],
    json_body: dict,
    provider: str,
    on_complete: Callable[[int | None, int | None], Awaitable[None]],
) -> tuple[int, dict[str, str], AsyncIterator[bytes]]:
    """
    Open an upstream streaming request, capture response status/headers immediately,
    and stream SSE bytes verbatim while sniffing trailing provider usage frames.
    """
    stream_ctx = client.stream("POST", upstream_url, json=json_body, headers=headers)
    upstream_resp = await stream_ctx.__aenter__()

    forward_headers: dict[str, str] = {}
    for key in ("content-type", "cache-control", "x-request-id"):
        if key in upstream_resp.headers:
            forward_headers[key] = upstream_resp.headers[key]

    async def _byte_generator() -> AsyncIterator[bytes]:
        captured_input_tokens: int | None = None
        captured_cached_tokens: int | None = None
        line_buffer = ""

        try:
            async for chunk in upstream_resp.aiter_bytes():
                yield chunk
                line_buffer += chunk.decode("utf-8", errors="ignore")
                while "\n" in line_buffer:
                    line, line_buffer = line_buffer.split("\n", 1)
                    stripped = line.strip()
                    if not stripped.startswith("data:"):
                        continue
                    data_str = stripped[5:].strip()
                    if not data_str or data_str == "[DONE]":
                        continue
                    try:
                        event_json = json.loads(data_str)
                    except json.JSONDecodeError:
                        continue
                    if isinstance(event_json, dict):
                        in_tok, cached_tok = parse_sse_usage_event(provider, event_json)
                        if in_tok is not None:
                            captured_input_tokens = in_tok
                        if cached_tok is not None:
                            captured_cached_tokens = cached_tok
        finally:
            await stream_ctx.__aexit__(None, None, None)
            await on_complete(captured_input_tokens, captured_cached_tokens)

    return upstream_resp.status_code, forward_headers, _byte_generator()
