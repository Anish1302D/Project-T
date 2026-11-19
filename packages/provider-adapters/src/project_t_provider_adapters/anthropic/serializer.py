"""Anthropic Messages request/response serializer."""

from __future__ import annotations

from copy import deepcopy
from typing import Any

from project_t_contracts import ContentType


def extract_anthropic_usage(payload: dict[str, Any]) -> tuple[int | None, int | None]:
    """Return (input_tokens, cached_input_tokens) from Anthropic JSON or SSE event."""
    # Direct response or message_delta usage; message_start nests inside message.usage
    usage = payload.get("usage")
    if not isinstance(usage, dict) and isinstance(payload.get("message"), dict):
        usage = payload["message"].get("usage")
    if not isinstance(usage, dict):
        return None, None

    raw_in = usage.get("input_tokens")
    if not isinstance(raw_in, int):
        return None, None
    cached = usage.get("cache_read_input_tokens")
    return raw_in, cached if isinstance(cached, int) else None


def optimize_anthropic_payload(
    payload: dict[str, Any],
    optimize_text_fn: Any,
) -> tuple[dict[str, Any], int, int]:
    """
    Optimize eligible text blocks in an Anthropic /v1/messages payload.

    Preserves tools, tool_choice, tool_use, and tool_result blocks verbatim.
    """
    updated = deepcopy(payload)
    orig_total = 0
    opt_total = 0

    system = updated.get("system")
    if isinstance(system, str) and system.strip():
        new_sys, o_tok, n_tok = optimize_text_fn(system, ContentType.DEVELOPER_PROMPT)
        updated["system"] = new_sys
        orig_total += o_tok
        opt_total += n_tok
    elif isinstance(system, list):
        for block in system:
            if isinstance(block, dict) and block.get("type") == "text" and isinstance(block.get("text"), str):
                if block["text"].strip():
                    new_txt, o_tok, n_tok = optimize_text_fn(block["text"], ContentType.DEVELOPER_PROMPT)
                    block["text"] = new_txt
                    orig_total += o_tok
                    opt_total += n_tok

    messages = updated.get("messages")
    if isinstance(messages, list):
        for msg in messages:
            if not isinstance(msg, dict) or msg.get("role") != "user":
                continue
            content = msg.get("content")
            if isinstance(content, str) and content.strip():
                new_txt, o_tok, n_tok = optimize_text_fn(content, None)
                msg["content"] = new_txt
                orig_total += o_tok
                opt_total += n_tok
            elif isinstance(content, list):
                for block in content:
                    if (
                        isinstance(block, dict)
                        and block.get("type") == "text"
                        and isinstance(block.get("text"), str)
                        and block["text"].strip()
                    ):
                        new_txt, o_tok, n_tok = optimize_text_fn(block["text"], None)
                        block["text"] = new_txt
                        orig_total += o_tok
                        opt_total += n_tok

    return updated, orig_total, opt_total
