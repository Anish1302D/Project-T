"""OpenAI request/response serializer and invariant-preserving payload optimizer."""

from __future__ import annotations

from copy import deepcopy
from typing import Any

from project_t_contracts import ContentType


def extract_openai_usage(payload: dict[str, Any]) -> tuple[int | None, int | None]:
    """Return (input_tokens, cached_input_tokens) from OpenAI JSON or SSE usage block."""
    usage = payload.get("usage")
    if not isinstance(usage, dict):
        return None, None
    raw_in = usage.get("prompt_tokens")
    if raw_in is None:
        raw_in = usage.get("input_tokens")
    if not isinstance(raw_in, int):
        return None, None

    cached: int | None = None
    details = usage.get("prompt_tokens_details") or usage.get("input_tokens_details")
    if isinstance(details, dict) and isinstance(details.get("cached_tokens"), int):
        cached = details["cached_tokens"]
    return raw_in, cached


def optimize_openai_chat_payload(
    payload: dict[str, Any],
    optimize_text_fn: Any,
) -> tuple[dict[str, Any], int, int]:
    """
    Optimize eligible text parts of an OpenAI Chat Completions payload.

    Strictly preserves tools, tool_choice, functions, response_format, and tool_calls.
    Returns (updated_payload, total_original_tokens, total_optimized_tokens).
    """
    updated = deepcopy(payload)
    orig_total = 0
    opt_total = 0

    messages = updated.get("messages")
    if not isinstance(messages, list):
        return updated, 0, 0

    for msg in messages:
        if not isinstance(msg, dict):
            continue
        role = msg.get("role")
        # Never mutate tool execution responses or assistant tool_calls envelopes
        if role == "tool" or msg.get("tool_calls") or msg.get("function_call"):
            continue
        if role not in {"user", "developer", "system"}:
            continue

        content = msg.get("content")
        if isinstance(content, str) and content.strip():
            # Skip pure JSON contract payloads when response_format demands JSON
            hint = ContentType.DEVELOPER_PROMPT if role in {"developer", "system"} else None
            new_text, o_tok, n_tok = optimize_text_fn(content, hint)
            msg["content"] = new_text
            orig_total += o_tok
            opt_total += n_tok
        elif isinstance(content, list):
            for part in content:
                if isinstance(part, dict) and part.get("type") == "text" and isinstance(part.get("text"), str):
                    if part["text"].strip():
                        new_text, o_tok, n_tok = optimize_text_fn(part["text"], None)
                        part["text"] = new_text
                        orig_total += o_tok
                        opt_total += n_tok

    return updated, orig_total, opt_total
