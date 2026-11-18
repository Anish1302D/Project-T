"""Immutable span-locking and sentinel masking/unmasking utilities."""

from __future__ import annotations

from dataclasses import dataclass

from project_t_contracts import ProtectedSpan

_SENTINEL_PREFIX = "\uE000PT_SPAN_"
_SENTINEL_SUFFIX = "\uE001"


@dataclass(frozen=True, slots=True)
class MaskedText:
    """Text with non-overlapping protected spans replaced by atomic sentinel tokens."""

    masked_text: str
    token_map: dict[str, str]
    locked_spans: tuple[ProtectedSpan, ...]


def select_non_overlapping_spans(
    spans: tuple[ProtectedSpan, ...] | list[ProtectedSpan],
) -> tuple[ProtectedSpan, ...]:
    """
    Merge overlapping spans deterministically, preferring earlier start and longer outer spans.
    """
    ordered = sorted(spans, key=lambda s: (s.start, -(s.end - s.start)))
    selected: list[ProtectedSpan] = []
    last_end = -1
    for span in ordered:
        if span.end <= span.start:
            continue
        if span.start >= last_end:
            selected.append(span)
            last_end = span.end
    return tuple(selected)


def mask_protected_spans(
    text: str,
    spans: tuple[ProtectedSpan, ...] | list[ProtectedSpan],
) -> MaskedText:
    """Replace non-overlapping protected spans with atomic private-use sentinel tokens."""
    locked = select_non_overlapping_spans(spans)
    if not locked:
        return MaskedText(masked_text=text, token_map={}, locked_spans=())

    chunks: list[str] = []
    token_map: dict[str, str] = {}
    cursor = 0

    for idx, span in enumerate(locked):
        # Guard against out-of-bounds or mismatched slice offsets
        if span.end > len(text) or text[span.start : span.end] != span.value:
            continue
        if span.start > cursor:
            chunks.append(text[cursor : span.start])
        token = f"{_SENTINEL_PREFIX}{idx:04d}{_SENTINEL_SUFFIX}"
        token_map[token] = span.value
        chunks.append(token)
        cursor = span.end

    if cursor < len(text):
        chunks.append(text[cursor:])

    return MaskedText(
        masked_text="".join(chunks),
        token_map=token_map,
        locked_spans=locked,
    )


def unmask_protected_spans(
    masked_text: str,
    token_map: dict[str, str],
) -> tuple[str, bool]:
    """
    Restore all sentinel tokens back to original locked span values.

    Returns (restored_text, all_tokens_intact). If any sentinel was lost or duplicated,
    all_tokens_intact is False so caller triggers immediate fallback.
    """
    restored = masked_text
    for token, original_value in token_map.items():
        if restored.count(token) != 1:
            return masked_text, False
        restored = restored.replace(token, original_value, 1)
    return restored, True
