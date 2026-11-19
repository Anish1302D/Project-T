"""Google Gemini generateContent request/response serializer."""

from __future__ import annotations

from copy import deepcopy
from typing import Any

from project_t_contracts import ContentType


def extract_google_usage(payload: dict[str, Any]) -> tuple[int | None, int | None]:
    """Return (input_tokens, cached_input_tokens) from Gemini usageMetadata."""
    usage = payload.get("usageMetadata")
    if not isinstance(usage, dict):
        return None, None
    raw_in = usage.get("promptTokenCount")
    if not isinstance(raw_in, int):
        return None, None
    cached = usage.get("cachedContentTokenCount")
    return raw_in, cached if isinstance(cached, int) else None


def optimize_google_payload(
    payload: dict[str, Any],
    optimize_text_fn: Any,
) -> tuple[dict[str, Any], int, int]:
    """
    Optimize eligible text parts in a Gemini generateContent payload.

    Preserves tools, toolConfig, generationConfig.responseSchema, functionCall, and functionResponse.
    """
    updated = deepcopy(payload)
    orig_total = 0
    opt_total = 0

    sys_inst = updated.get("systemInstruction")
    if isinstance(sys_inst, dict) and isinstance(sys_inst.get("parts"), list):
        for part in sys_inst["parts"]:
            if isinstance(part, dict) and isinstance(part.get("text"), str) and part["text"].strip():
                new_txt, o_tok, n_tok = optimize_text_fn(part["text"], ContentType.DEVELOPER_PROMPT)
                part["text"] = new_txt
                orig_total += o_tok
                opt_total += n_tok

    contents = updated.get("contents")
    if isinstance(contents, list):
        for entry in contents:
            if not isinstance(entry, dict):
                continue
            role = entry.get("role", "user")
            if role not in {"user", None}:
                continue
            parts = entry.get("parts")
            if not isinstance(parts, list):
                continue
            for part in parts:
                if (
                    isinstance(part, dict)
                    and "functionCall" not in part
                    and "functionResponse" not in part
                    and isinstance(part.get("text"), str)
                    and part["text"].strip()
                ):
                    new_txt, o_tok, n_tok = optimize_text_fn(part["text"], None)
                    part["text"] = new_txt
                    orig_total += o_tok
                    opt_total += n_tok

    return updated, orig_total, opt_total
