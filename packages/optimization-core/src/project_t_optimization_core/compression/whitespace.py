"""Mode-aware safe whitespace compaction."""

from __future__ import annotations

from project_t_contracts import ContentType, OptimizationMode

from ..deduplication.normalizer import normalize_safe_whitespace


def compact_whitespace(
    text: str,
    *,
    content_type: ContentType,
    mode: OptimizationMode,
) -> tuple[str, bool]:
    """
    Compact excess whitespace respecting mode policy and indentation-sensitive formats.

    Returns (result_text, applied).
    """
    if not text:
        return text, False

    preserve_indent = True
    max_blank_lines = 2 if mode == OptimizationMode.SAFE else 1
    compacted = normalize_safe_whitespace(
        text,
        content_type=content_type,
        preserve_indentation=preserve_indent,
        max_blank_lines=max_blank_lines,
    )
    return compacted, compacted != text
