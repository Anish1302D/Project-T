"""Deterministic P0 rule-based prose filler and verbosity compression."""

from __future__ import annotations

import re

from project_t_contracts import ContentType, OptimizationMode

from .._segments import split_segments

_NON_PROSE_TYPES = frozenset(
    {
        ContentType.SOURCE_CODE,
        ContentType.JSON,
        ContentType.TOOL_RESULT,
        ContentType.TERMINAL_OUTPUT,
    }
)

# Inline code, quoted literals, and HTTP URLs that must remain untouched by prose rules.
_INLINE_PROTECT_RE = re.compile(r"(`[^`\n]+`|\"[^\"\n]+\"|https?://[^\s)>]+)")

# (pattern, replacement) ordered conservatively to preserve instruction & constraint semantics.
_OPENER_RULES: tuple[tuple[re.Pattern[str], str], ...] = (
    (
        re.compile(
            r"(?i)^(?:hello|hi|hey)[,!\s]+(?:could you |can you |would you )?(?:please )?(?:help me (?:by |to )?)?",
        ),
        "",
    ),
    (
        re.compile(
            r"(?i)^(?:i would (?:really )?appreciate it if you could|could you please|can you please|would you please)\s+"
        ),
        "",
    ),
    (
        re.compile(r"(?i)^please help me (?:to )?"),
        "",
    ),
)

_PHRASE_RULES: tuple[tuple[re.Pattern[str], str], ...] = (
    (re.compile(r"(?i)\bin order to\b"), "to"),
    (re.compile(r"(?i)\bdue to the fact that\b"), "because"),
    (re.compile(r"(?i)\bfor the purpose of\b"), "for"),
    (re.compile(r"(?i)\bat this point in time\b"), "now"),
    (re.compile(r"(?i)\bin the event that\b"), "if"),
    (re.compile(r"(?i)\ba large number of\b"), "many"),
    (re.compile(r"(?i)\bwith regard to\b"), "regarding"),
    (re.compile(r"(?i)\btake a look at\b"), "inspect"),
    (re.compile(r"(?i)\bmake sure to\b"), "ensure you"),
    (re.compile(r"(?i)\bkindly\s+"), ""),
)


def _rewrite_unprotected_span(span: str, *, mode: OptimizationMode) -> str:
    updated = span
    for pattern, repl in _PHRASE_RULES:
        updated = pattern.sub(repl, updated)

    if mode == OptimizationMode.AGGRESSIVE:
        updated = re.sub(r"(?i)\bplease\s+", "", updated)

    # Tidy any double spaces introduced inside prose without disturbing newlines
    updated = re.sub(r"[ \t]{2,}", " ", updated)
    updated = re.sub(r"\s+([,.;:?!])", r"\1", updated)
    return updated


def _apply_prose_line_rules(line: str, *, mode: OptimizationMode) -> str:
    if not line.strip():
        return line

    # Do not modify Markdown headings, bullet prefixes, or constraint lead-ins blindly
    leading_ws = line[: len(line) - len(line.lstrip(" \t"))]
    body = line[len(leading_ws) :]

    # Protect inline code/quotes/URLs by splitting around them
    tokens = _INLINE_PROTECT_RE.split(body)
    rebuilt: list[str] = []
    for idx, chunk in enumerate(tokens):
        if idx % 2 == 1:  # protected match
            rebuilt.append(chunk)
        else:
            rebuilt.append(_rewrite_unprotected_span(chunk, mode=mode))
    candidate = "".join(rebuilt).strip()

    # Apply ceremonial opener removal only at sentence/line start when not inside a quote
    for opener_re, repl in _OPENER_RULES:
        candidate = opener_re.sub(repl, candidate)

    if candidate and candidate[0].islower() and body[0].isupper():
        candidate = candidate[0].upper() + candidate[1:]

    return f"{leading_ws}{candidate}" if candidate else ""


def _ranges_overlap(
    start: int,
    end: int,
    protected_ranges: tuple[tuple[int, int], ...],
) -> bool:
    return any(not (end <= p_start or start >= p_end) for p_start, p_end in protected_ranges)


def compress_prose_rules(
    text: str,
    *,
    content_type: ContentType,
    mode: OptimizationMode,
    protected_ranges: tuple[tuple[int, int], ...] = (),
) -> tuple[str, bool]:
    """
    Apply deterministic rule-based prose compression outside protected spans and code blocks.

    Disabled in SAFE mode and for non-prose content types (source_code, json, terminal_output, tool_result).
    """
    if mode == OptimizationMode.SAFE or content_type in _NON_PROSE_TYPES or not text.strip():
        return text, False

    out_segments: list[str] = []
    for seg in split_segments(text):
        if seg.kind in {"code_fence", "json_block"}:
            out_segments.append(seg.text)
            continue

        lines = seg.text.splitlines(keepends=True)
        cursor = seg.start
        processed_lines: list[str] = []
        for raw_line in lines:
            line_start = cursor
            line_end = cursor + len(raw_line)
            cursor = line_end

            if _ranges_overlap(line_start, line_end, protected_ranges):
                processed_lines.append(raw_line)
                continue

            newline_suffix = ""
            if raw_line.endswith("\r\n"):
                body, newline_suffix = raw_line[:-2], "\r\n"
            elif raw_line.endswith("\n"):
                body, newline_suffix = raw_line[:-1], "\n"
            else:
                body = raw_line

            rewritten = _apply_prose_line_rules(body, mode=mode)
            processed_lines.append(f"{rewritten}{newline_suffix}")

        out_segments.append("".join(processed_lines))

    result = "".join(out_segments)
    return (result, True) if result != text else (text, False)
