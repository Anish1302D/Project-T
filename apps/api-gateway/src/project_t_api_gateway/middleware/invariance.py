"""Structural and tool-contract invariance verification prior to upstream dispatch."""

from __future__ import annotations

from typing import Any

_TOP_LEVEL_INVARIANT_KEYS: tuple[str, ...] = (
    "model",
    "tools",
    "functions",
    "function_call",
    "tool_choice",
    "toolConfig",
    "response_format",
    "generationConfig",
    "stream",
    "temperature",
    "top_p",
    "seed",
    "max_tokens",
    "max_output_tokens",
    "stream_options",
)


def _strip_optimizable_text(provider: str, payload: dict[str, Any]) -> dict[str, Any]:
    """
    Create a structural skeleton removing only eligible plain-text fields so
    every tool call, schema, role, and non-text block can be verified 1:1.
    """
    if provider == "openai":
        msgs = payload.get("messages")
        skel_msgs = []
        if isinstance(msgs, list):
            for msg in msgs:
                if not isinstance(msg, dict):
                    skel_msgs.append(msg)
                    continue
                copy_msg = dict(msg)
                role = copy_msg.get("role")
                # Tool messages and tool_calls messages must remain 100% identical (not stripped!)
                if role in {"user", "developer", "system"} and not copy_msg.get("tool_calls") and not copy_msg.get("function_call"):
                    if isinstance(copy_msg.get("content"), str):
                        copy_msg["content"] = "<OPTIMIZED_TEXT>"
                    elif isinstance(copy_msg.get("content"), list):
                        copy_msg["content"] = [
                            {"type": "text", "text": "<OPTIMIZED_TEXT>"}
                            if isinstance(p, dict) and p.get("type") == "text"
                            else p
                            for p in copy_msg["content"]
                        ]
                skel_msgs.append(copy_msg)
        return {"messages": skel_msgs}

    if provider == "anthropic":
        skel_sys = payload.get("system")
        if isinstance(skel_sys, str):
            skel_sys = "<OPTIMIZED_TEXT>"
        elif isinstance(skel_sys, list):
            skel_sys = [
                {**b, "text": "<OPTIMIZED_TEXT>"}
                if isinstance(b, dict) and b.get("type") == "text"
                else b
                for b in skel_sys
            ]
        msgs = payload.get("messages")
        skel_msgs = []
        if isinstance(msgs, list):
            for msg in msgs:
                if not isinstance(msg, dict) or msg.get("role") != "user":
                    skel_msgs.append(msg)
                    continue
                copy_msg = dict(msg)
                if isinstance(copy_msg.get("content"), str):
                    copy_msg["content"] = "<OPTIMIZED_TEXT>"
                elif isinstance(copy_msg.get("content"), list):
                    copy_msg["content"] = [
                        {**b, "text": "<OPTIMIZED_TEXT>"}
                        if isinstance(b, dict) and b.get("type") == "text"
                        else b
                        for b in copy_msg["content"]
                    ]
                skel_msgs.append(copy_msg)
        return {"system": skel_sys, "messages": skel_msgs}

    if provider == "google":
        contents = payload.get("contents")
        skel_contents = []
        if isinstance(contents, list):
            for entry in contents:
                if not isinstance(entry, dict) or entry.get("role", "user") not in {"user", None}:
                    skel_contents.append(entry)
                    continue
                copy_entry = dict(entry)
                if isinstance(copy_entry.get("parts"), list):
                    copy_entry["parts"] = [
                        {"text": "<OPTIMIZED_TEXT>"}
                        if isinstance(p, dict)
                        and "functionCall" not in p
                        and "functionResponse" not in p
                        and "text" in p
                        else p
                        for p in copy_entry["parts"]
                    ]
                skel_contents.append(copy_entry)
        return {"contents": skel_contents}

    return {}


def verify_provider_payload_invariance(
    provider: str,
    original: dict[str, Any],
    candidate: dict[str, Any],
) -> tuple[bool, str | None]:
    """
    Guarantee zero silent modification of tool schemas, function arguments,
    structured-output contracts, or model/sampling settings.
    """
    for key in _TOP_LEVEL_INVARIANT_KEYS:
        if original.get(key) != candidate.get(key):
            return False, f"invariant_top_level_key_changed:{key}"

    if set(original.keys()) != set(candidate.keys()):
        return False, "invariant_top_level_keyset_changed"

    orig_skel = _strip_optimizable_text(provider, original)
    cand_skel = _strip_optimizable_text(provider, candidate)
    if orig_skel != cand_skel:
        return False, "invariant_message_or_tool_structure_changed"

    return True, None
