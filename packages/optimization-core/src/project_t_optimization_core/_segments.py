"""Shared segment-splitting utilities for fenced code and JSON blocks."""

from __future__ import annotations

import json
import re
from dataclasses import dataclass
from typing import Literal

SegmentKind = Literal["prose", "code_fence", "json_block", "log_block"]

_FENCE_RE = re.compile(r"(```[^\n]*\n[\s\S]*?\n```)", re.MULTILINE)


@dataclass(frozen=True, slots=True)
class Segment:
    """Typed span slice inside an input payload."""

    kind: SegmentKind
    start: int
    end: int
    text: str
    language: str | None = None


def try_parse_json(text: str) -> object | None:
    """Return parsed JSON value if text is a standalone JSON object/array, else None."""
    stripped = text.strip()
    if not stripped or stripped[0] not in "{[":
        return None
    try:
        return json.loads(stripped)
    except json.JSONDecodeError:
        return None


def split_segments(content: str) -> tuple[Segment, ...]:
    """Partition text into prose and fenced code/JSON segments."""
    segments: list[Segment] = []
    cursor = 0
    for match in _FENCE_RE.finditer(content):
        if match.start() > cursor:
            prose_slice = content[cursor : match.start()]
            if prose_slice:
                segments.append(
                    Segment(kind="prose", start=cursor, end=match.start(), text=prose_slice)
                )
        fence_text = match.group(1)
        first_line_end = fence_text.find("\n")
        lang_tag = fence_text[3:first_line_end].strip().lower() if first_line_end > 3 else ""
        body = fence_text[first_line_end + 1 : -3] if first_line_end != -1 else ""
        is_json_fence = lang_tag == "json" or try_parse_json(body) is not None
        kind: SegmentKind = "json_block" if is_json_fence else "code_fence"
        segments.append(
            Segment(
                kind=kind,
                start=match.start(),
                end=match.end(),
                text=fence_text,
                language=lang_tag or ("json" if is_json_fence else None),
            )
        )
        cursor = match.end()

    if cursor < len(content):
        tail = content[cursor:]
        if tail:
            segments.append(Segment(kind="prose", start=cursor, end=len(content), text=tail))

    return tuple(segments)
