"""Golden regression tests for edge cases, safety guarantees, and rollback behavior."""

from project_t_contracts import (
    ContentType,
    OptimizationMode,
    OptimizationRequestWire,
    OptimizationStatus,
)

from project_t_optimization_core.pipeline import PipelineOrchestrator


def test_regression_tiny_or_whitespace_inputs_never_corrupt() -> None:
    orchestrator = PipelineOrchestrator()

    for payload in ["x", "   \n  ", "Fix auth.py."]:
        exec_res = orchestrator.optimize(OptimizationRequestWire(content=payload))
        assert exec_res.result.optimized_content == payload
        assert exec_res.result.tokens.saved == 0
        assert exec_res.result.original_content == payload


def test_regression_dense_json_and_similar_functions_remain_intact() -> None:
    orchestrator = PipelineOrchestrator()

    json_payload = '{"a": 1, "b": {"c": "in order to test"}, "d": [1, 2, 3]}'
    json_exec = orchestrator.optimize(
        OptimizationRequestWire(
            content=json_payload,
            content_type=ContentType.JSON,
            mode=OptimizationMode.AGGRESSIVE,
        )
    )
    assert json_exec.result.optimized_content == json_payload
    assert json_exec.result.validation.passed is True

    similar_code = (
        "def add_user_v1(user_id: int) -> int:\n"
        "    return user_id + 1\n\n"
        "def add_user_v2(user_id: int) -> int:\n"
        "    return user_id + 2\n"
    )
    code_exec = orchestrator.optimize(
        OptimizationRequestWire(
            content=similar_code,
            content_type=ContentType.SOURCE_CODE,
            mode=OptimizationMode.AGGRESSIVE,
        )
    )
    assert code_exec.result.optimized_content == similar_code
    assert code_exec.status == OptimizationStatus.FALLBACK_NO_SAVINGS


def test_regression_validator_failure_triggers_safe_rollback() -> None:
    class _BrokenValidator:
        def validate(self, **kwargs):
            from project_t_contracts import ValidationSummary
            from project_t_optimization_core.validation import ValidationReport

            return ValidationReport(
                summary=ValidationSummary(
                    passed=False,
                    constraints_preserved=False,
                    identifiers_preserved=True,
                    structure_preserved=True,
                    quality_score=0.25,
                ),
                intent_score=1.0,
                constraint_score=0.0,
                structure_score=1.0,
                reference_score=1.0,
                failure_reasons=("simulated_constraint_loss",),
            )

    orchestrator = PipelineOrchestrator(validator=_BrokenValidator())  # type: ignore[arg-type]
    prompt = "Could you please fix the bug in order to deploy cleanly?"
    exec_res = orchestrator.optimize(
        OptimizationRequestWire(content=prompt, mode=OptimizationMode.BALANCED)
    )
    assert exec_res.status == OptimizationStatus.FALLBACK_VALIDATION_FAILED
    assert exec_res.result.optimized_content == prompt
    assert exec_res.result.tokens.saved == 0
    assert "fallback_validation_failed" in exec_res.result.warnings
