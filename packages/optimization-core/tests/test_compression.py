"""Unit tests for rule-based prose compression and terminal log extraction."""

from project_t_contracts import ContentType, OptimizationMode

from project_t_optimization_core.compression import (
    compact_whitespace,
    compress_prose_rules,
    compress_terminal_output,
)


def test_safe_mode_never_rewrites_prose_and_preserves_identifiers() -> None:
    prompt = "Could you please check `verify_jwt_token` in order to fix https://example.com/api/v1/login?"
    unchanged, applied_safe = compress_prose_rules(
        prompt,
        content_type=ContentType.DEVELOPER_PROMPT,
        mode=OptimizationMode.SAFE,
    )
    assert applied_safe is False
    assert unchanged == prompt

    compressed, applied_balanced = compress_prose_rules(
        prompt,
        content_type=ContentType.DEVELOPER_PROMPT,
        mode=OptimizationMode.BALANCED,
    )
    assert applied_balanced is True
    assert "`verify_jwt_token`" in compressed
    assert "https://example.com/api/v1/login" in compressed
    assert "in order to" not in compressed
    assert "Could you please" not in compressed


def test_prose_rules_respect_protected_ranges_and_code_fences() -> None:
    text = (
        "In order to preserve exact wording here.\n"
        "Hello, could you please fix the bug in order to deploy.\n"
        "```python\n# in order to test fenced preservation\nx = 'could you please'\n```\n"
    )
    # Protect the entire first line from modification
    first_line_end = text.index("\n") + 1
    out, applied = compress_prose_rules(
        text,
        content_type=ContentType.DEVELOPER_PROMPT,
        mode=OptimizationMode.BALANCED,
        protected_ranges=((0, first_line_end),),
    )
    assert applied is True
    assert out.startswith("In order to preserve exact wording here.\n")
    assert "# in order to test fenced preservation" in out
    assert "x = 'could you please'" in out


def test_whitespace_compaction_respects_mode_and_code() -> None:
    text = "First paragraph.\n\n\n\nSecond paragraph."
    safe_out, _ = compact_whitespace(text, content_type=ContentType.PROMPT, mode=OptimizationMode.SAFE)
    bal_out, _ = compact_whitespace(text, content_type=ContentType.PROMPT, mode=OptimizationMode.BALANCED)
    assert safe_out == "First paragraph.\n\n\nSecond paragraph."
    assert bal_out == "First paragraph.\n\nSecond paragraph."


def test_terminal_log_compression_retains_diagnostics_and_strips_ansi() -> None:
    passing_noise = "\n".join(f"\x1b[32mPASS\x1b[0m tests/unit/test_ok_{i}.py" for i in range(40))
    raw_log = (
        "$ pytest tests/\n"
        f"{passing_noise}\n"
        "WARNING: Deprecated JWT config key detected near auth check\n"
        "Traceback (most recent call last):\n"
        '  File "src/auth/jwt.py", line 42, in validate_token\n'
        "    raise ValueError('expired signature')\n"
        "ValueError: expired signature\n"
        "FAILED tests/test_auth.py::test_expired_jwt\n"
        "=== 1 failed, 40 passed in 1.23s ===\n"
        "Exit code: 1\n"
    )
    res = compress_terminal_output(raw_log, command="pytest tests/", exit_code=1, context_lines=2)
    assert res.applied is True
    assert "\x1b[" not in res.compressed_text
    assert "$ pytest tests/" in res.compressed_text
    assert "Exit code: 1" in res.compressed_text
    assert "ValueError: expired signature" in res.compressed_text
    assert 'File "src/auth/jwt.py", line 42' in res.compressed_text
    assert "WARNING: Deprecated JWT config key" in res.compressed_text
    assert "FAILED tests/test_auth.py::test_expired_jwt" in res.compressed_text
    assert "1 failed, 40 passed" in res.compressed_text
    assert "lines omitted" in res.compressed_text
    assert len(res.compressed_text) < len(raw_log)
