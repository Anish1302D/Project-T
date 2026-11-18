"""Unit tests for QualityValidator hard invariants, diagnostic Q, and PipelineOrchestrator."""

from project_t_contracts import (
    ContentType,
    OptimizationFlags,
    OptimizationMode,
    OptimizationRequestWire,
    OptimizationStatus,
)

from project_t_optimization_core.constraints import ConstraintExtractor
from project_t_optimization_core.pipeline import PipelineConfig, PipelineOrchestrator
from project_t_optimization_core.validation import QualityValidator


def test_validator_rejects_lost_constraint_lost_identifier_and_broken_json() -> None:
    validator = QualityValidator()
    prompt = (
        "Update `verifyJwtToken` in src/auth/jwt.py.\n"
        "Do not change the database schema."
    )
    analysis = ConstraintExtractor().extract(prompt)

    ok = validator.validate(
        original=prompt,
        candidate=prompt,
        content_type=ContentType.DEVELOPER_PROMPT,
        analysis=analysis,
    )
    assert ok.summary.passed is True
    assert ok.summary.quality_score == 1.0

    dropped_constraint = validator.validate(
        original=prompt,
        candidate="Update `verifyJwtToken` in src/auth/jwt.py.",
        content_type=ContentType.DEVELOPER_PROMPT,
        analysis=analysis,
    )
    assert dropped_constraint.summary.passed is False
    assert dropped_constraint.summary.constraints_preserved is False

    dropped_ident = validator.validate(
        original=prompt,
        candidate="Update token checker in src/auth/jwt.py.\nDo not change the database schema.",
        content_type=ContentType.DEVELOPER_PROMPT,
        analysis=analysis,
    )
    assert dropped_ident.summary.passed is False
    assert dropped_ident.summary.identifiers_preserved is False

    bad_json = validator.validate(
        original='{"user_id": 1, "active": true}',
        candidate='{"user_id": 1}',
        content_type=ContentType.JSON,
        analysis=ConstraintExtractor().extract('{"user_id": 1, "active": true}'),
    )
    assert bad_json.summary.passed is False
    assert bad_json.summary.structure_preserved is False


def test_pipeline_optimizes_verbose_prompt_while_preserving_constraints_and_symbols() -> None:
    orchestrator = PipelineOrchestrator()
    repeated_context = (
        "Context block: The middleware verifies bearer headers on POST /api/v1/login requests "
        "before dispatching downstream handlers."
    )
    prompt = (
        "Hello, could you please help me by fixing `verifyJwtToken` in src/auth/jwt.py "
        "in order to resolve token expiry errors at this point in time?\n\n"
        f"{repeated_context}\n\n"
        f"{repeated_context}\n\n"
        "Do not change the database schema.\n\n\n\n"
    )

    execution = orchestrator.optimize(
        OptimizationRequestWire(
            content=prompt,
            mode=OptimizationMode.BALANCED,
            optimization=OptimizationFlags(
                deduplicate=True,
                semantic_compression=False,
                preserve_identifiers=True,
            ),
        )
    )
    res = execution.result
    assert execution.status == OptimizationStatus.VALIDATED
    assert res.original_content == prompt
    assert res.tokens.saved > 0
    assert res.tokens.optimized < res.tokens.original
    assert res.validation.passed is True
    assert res.validation.constraints_preserved is True
    assert res.validation.identifiers_preserved is True
    assert "verifyJwtToken" in res.optimized_content
    assert "src/auth/jwt.py" in res.optimized_content
    assert "POST /api/v1/login" in res.optimized_content
    assert "Do not change the database schema." in res.optimized_content
    assert "exact_deduplication" in res.optimization.methods


def test_pipeline_falls_back_cleanly_when_savings_below_threshold_or_error() -> None:
    orchestrator = PipelineOrchestrator(
        config=PipelineConfig(min_meaningful_savings_tokens=50)
    )
    short_prompt = "Check `verify_jwt` in auth.py."
    execution = orchestrator.optimize(OptimizationRequestWire(content=short_prompt))
    assert execution.status == OptimizationStatus.FALLBACK_NO_SAVINGS
    assert execution.result.optimized_content == short_prompt
    assert execution.result.tokens.saved == 0
    assert "fallback_no_meaningful_savings" in execution.result.warnings


def test_pipeline_semantic_compression_remains_off_by_default() -> None:
    class _SpySemanticCompressor:
        called = False

        def compress(self, text: str, *, content_type: ContentType, mode: OptimizationMode) -> str:
            self.called = True
            return "shorter"

    spy = _SpySemanticCompressor()
    orchestrator = PipelineOrchestrator(semantic_compressor=spy)
    orchestrator.optimize(
        OptimizationRequestWire(
            content="Please inspect " + ("verbose prose filler " * 40),
            mode=OptimizationMode.AGGRESSIVE,
            optimization=OptimizationFlags(semantic_compression=True),
        )
    )
    assert spy.called is False
