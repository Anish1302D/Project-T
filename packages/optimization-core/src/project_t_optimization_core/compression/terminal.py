"""Deterministic P0 terminal and test-runner log compressor."""

from __future__ import annotations

import re
from dataclasses import dataclass

_ANSI_ESCAPE_RE = re.compile(r"\x1b\[[0-9;?]*[A-Za-z]")

_ERROR_OR_TRACE_RE = re.compile(
    r"(?:"
    r"Traceback \(most recent call last\):|"
    r"^\s*File \"[^\"]+\", line \d+|"
    r"^\s*at\s+.*:\d+:\d+|"
    r"\b(?:Error|Exception|AssertionError|TypeError|ValueError|KeyError|RuntimeError|SyntaxError|ModuleNotFoundError)\b|"
    r"^\s*(?:FAILED|FAIL|ERROR|ERR!)\b|"
    r"npm ERR!|"
    r"\bexit(?:ed)?\s+(?:with\s+)?(?:code|status)\s*[:=]?\s*\d+|"
    r"^\s*>\s+\S+.*:\d+"
    r")",
    re.IGNORECASE,
)

_WARNING_RE = re.compile(r"\b(?:WARNING|WARN|DeprecationWarning|UserWarning)\b")
_TEST_SUMMARY_RE = re.compile(
    r"(?:"
    r"=+\s*(?:\d+\s+(?:failed|passed|skipped|error|errors).*)=+|"
    r"\b\d+\s+(?:passed|failed|skipped|errors?)\b|"
    r"^\s*(?:Test Files|Tests)\s+\d+"
    r")",
    re.IGNORECASE,
)
_FILE_LINE_RE = re.compile(r"(?:[A-Za-z]:)?[\w./\\-]+\.\w{1,6}:\d+(?::\d+)?")
_COMMAND_LINE_RE = re.compile(r"^\s*(?:\$|>|#|Command:|Exit code:)", re.IGNORECASE)


@dataclass(frozen=True, slots=True)
class TerminalCompressionResult:
    """Result of compressing terminal/log output while retaining diagnostic signals."""

    compressed_text: str
    original_line_count: int
    kept_line_count: int
    omitted_line_count: int
    applied: bool


def strip_ansi_and_progress(raw_output: str) -> str:
    """Remove ANSI CSI sequences and terminal carriage-return progress spinner overwrites."""
    no_ansi = _ANSI_ESCAPE_RE.sub("", raw_output)
    normalized_lines: list[str] = []
    for raw_line in no_ansi.replace("\r\n", "\n").split("\n"):
        # For spinner lines using '\r', retain only the final overwritten frame
        if "\r" in raw_line:
            parts = [p for p in raw_line.split("\r") if p]
            normalized_lines.append(parts[-1] if parts else "")
        else:
            normalized_lines.append(raw_line)
    return "\n".join(normalized_lines)


def compress_terminal_output(
    output: str,
    *,
    command: str | None = None,
    exit_code: int | None = None,
    context_lines: int = 5,
) -> TerminalCompressionResult:
    """
    Extract actionable failure diagnostics from verbose terminal/test output.

    Preserves all 7 categories specified in Section 7.7:
    command, exit code, first error, stack trace frames, file paths/lines,
    failure-adjacent warnings, surrounding context window, and test summary counts.
    """
    cleaned = strip_ansi_and_progress(output)
    lines = cleaned.splitlines()
    if not lines:
        return TerminalCompressionResult(
            compressed_text="",
            original_line_count=0,
            kept_line_count=0,
            omitted_line_count=0,
            applied=False,
        )

    keep_indices: set[int] = set()
    error_indices: list[int] = []

    for idx, line in enumerate(lines):
        if _COMMAND_LINE_RE.search(line):
            keep_indices.add(idx)
        if _TEST_SUMMARY_RE.search(line):
            keep_indices.add(idx)
        if _ERROR_OR_TRACE_RE.search(line):
            error_indices.append(idx)
            start = max(0, idx - context_lines)
            end = min(len(lines), idx + context_lines + 1)
            keep_indices.update(range(start, end))
        elif _FILE_LINE_RE.search(line) and any(abs(idx - err_i) <= context_lines * 2 for err_i in error_indices):
            keep_indices.add(idx)

    # Preserve warnings located near failures or when no explicit error matched yet
    for idx, line in enumerate(lines):
        if _WARNING_RE.search(line):
            if not error_indices or any(abs(idx - err_i) <= max(10, context_lines * 2) for err_i in error_indices):
                keep_indices.add(idx)

    # If no diagnostic markers were recognized at all, retain head + tail safely
    if not keep_indices:
        head_tail = min(len(lines), max(10, context_lines * 2))
        if len(lines) <= head_tail * 2:
            keep_indices.update(range(len(lines)))
        else:
            keep_indices.update(range(head_tail))
            keep_indices.update(range(len(lines) - head_tail, len(lines)))

    ordered_kept = sorted(keep_indices)
    output_lines: list[str] = []
    if command is not None and not any(command in lines[i] for i in ordered_kept[:3]):
        output_lines.append(f"Command: {command}")
    if exit_code is not None and not any(str(exit_code) in lines[i] for i in ordered_kept):
        output_lines.append(f"Exit code: {exit_code}")

    prev_idx = -1
    omitted_total = 0
    for idx in ordered_kept:
        gap = idx - prev_idx - 1
        if prev_idx != -1 and gap > 1:
            output_lines.append(f"... [{gap} lines omitted] ...")
            omitted_total += gap
        elif prev_idx == -1 and idx > 0:
            output_lines.append(f"... [{idx} leading lines omitted] ...")
            omitted_total += idx
        elif gap == 1:
            output_lines.append(lines[idx - 1])
        output_lines.append(lines[idx])
        prev_idx = idx

    trailing_gap = len(lines) - 1 - prev_idx
    if trailing_gap > 0:
        output_lines.append(f"... [{trailing_gap} trailing lines omitted] ...")
        omitted_total += trailing_gap

    candidate = "\n".join(output_lines)
    # Fail-safe: never return an expanded output over already concise terminal logs
    if len(candidate) >= len(cleaned):
        if cleaned != output and len(cleaned) < len(output):
            return TerminalCompressionResult(
                compressed_text=cleaned,
                original_line_count=len(lines),
                kept_line_count=len(lines),
                omitted_line_count=0,
                applied=True,
            )
        return TerminalCompressionResult(
            compressed_text=output,
            original_line_count=len(lines),
            kept_line_count=len(lines),
            omitted_line_count=0,
            applied=False,
        )

    return TerminalCompressionResult(
        compressed_text=candidate,
        original_line_count=len(lines),
        kept_line_count=len(ordered_kept),
        omitted_line_count=omitted_total,
        applied=candidate != output,
    )
