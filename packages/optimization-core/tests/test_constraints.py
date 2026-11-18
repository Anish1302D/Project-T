"""Unit tests for ConstraintExtractor and 10-category protected-span locking."""

from project_t_optimization_core.constraints import (
    ConstraintExtractor,
    mask_protected_spans,
    unmask_protected_spans,
)


def test_extracts_all_10_protected_span_categories() -> None:
    content = (
        "Fix the auth check in src/auth/jwt.py#L42 for GET /api/v1/optimize.\n"
        "from project_t_contracts import OptimizationRequestWire\n"
        "Preserve `verifyJwtToken`, ValidationError, ERR_INVALID_TOKEN, PROJECT_T_PORT, 127.0.0.1:4765, and v0.1.0.\n"
        "Call optimize_prompt and return valid JSON matching:\n"
        '```json\n{"user_id": 1, "strict_mode": true}\n```\n'
        "Do not change the database schema.\n"
    )
    analysis = ConstraintExtractor().extract(content)
    categories = {span.category for span in analysis.protected_spans}

    expected_categories = {
        "identifier",
        "import_or_type",
        "api_endpoint",
        "error_code_or_message",
        "file_path_or_line",
        "json_key_or_schema",
        "explicit_constraint",
        "tool_name_or_arg",
        "version_or_config",
        "output_format",
    }
    assert expected_categories.issubset(categories)
    assert "Do not change the database schema." in analysis.constraints.constraints
    assert any("verifyJwtToken" == s.value for s in analysis.protected_spans)
    assert any("src/auth/jwt.py#L42" == s.value for s in analysis.protected_spans)


def test_python_ast_identifiers_and_sentinel_masking_round_trip() -> None:
    content = (
        "Could you please inspect this function in order to find bugs?\n"
        "```python\ndef calculate_token_delta(original_count: int, optimized_count: int) -> int:\n"
        "    return original_count - optimized_count\n```\n"
        "Never modify `calculate_token_delta` signature."
    )
    analysis = ConstraintExtractor().extract(content)
    id_values = {s.value for s in analysis.protected_spans if s.category == "identifier"}
    assert {"calculate_token_delta", "original_count", "optimized_count"}.issubset(id_values)

    masked = mask_protected_spans(content, analysis.protected_spans)
    assert masked.token_map
    restored, intact = unmask_protected_spans(masked.masked_text, masked.token_map)
    assert intact is True
    assert restored == content
