"""Stage 1 safe whitespace and line-ending normalization."""

from __future__ import annotations

import re

from project_t_contracts import ContentType

from .._segments import split_segments


def normalize_line_endings(text: str) -> str:
    """Normalize CRLF/CR line endings to LF without altering indentation."""
    return text.replace("\r\n", "\n").replace("\r", "\n")


def _collapse_prose_segment(
    segment_text: str,
    *,
    preserve_indentation: bool,
    max_blank_lines: int,
) -> str:
    lines = segment_text.split("\n")
    cleaned_lines: list[str] = []
    for line in lines:
        trimmed = line.rstrip() if preserve_indentation else re.sub(r"[ \t]{2,}", " ", line.strip())
        cleaned_lines.append(trimmed)
    joined = "\n".join(cleaned_lines)
    max_newlines = max(1, max_blank_lines + 1)
    return re.sub(rf"\n{{{max_newlines + 1},}}", "\n" * max_newlines, joined)


def normalize_safe_whitespace(
    text: str,
    *,
    content_type: ContentType | None = None,
    preserve_indentation: bool = True,
    max_blank_lines: int = 2,
) -> str:
    """
    Safely normalize line endings and excess whitespace without corrupting code or JSON.

    - For SOURCE_CODE, JSON, and TOOL_RESULT, only line endings (\r\n -> \n) and
      excessive trailing blank lines at EOF are normalized; indentation and strings remain intact.
    - For prose/prompts/docs/conversations, fenced code and JSON blocks stay untouched while
      surrounding prose trims trailing line whitespace and excessive blank runs.
    """
    normalized = normalize_line_endings(text)
    if content_type in {ContentType.SOURCE_CODE, ContentType.JSON, ContentType.TOOL_RESULT}:
        # Keep indentation and internal blank lines intact; only collapse extreme EOF trailing blanks.
        return re.sub(r"\n{3,}$", "\n", normalized)

    out_parts: list[str] = []
    for seg in split_segments(normalized):
        if seg.kind in {"code_fence", "json_block"}:
            out_parts.append(seg.text)
        else:
            out_parts.append(
                _collapse_prose_segment(
                    seg.text,
                    preserve_indentation=preserve_indentation,
                    max_blank_lines=max_blank_lines,
                )
            )
    return "".join(out_parts).strip("\n") if normalized.strip() else ""
