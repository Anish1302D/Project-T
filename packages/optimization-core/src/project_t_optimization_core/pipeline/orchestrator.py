"""Deterministic-first 10-stage pipeline orchestrator with fail-safe rollback."""

from __future__ import annotations

import time
import uuid
from dataclasses import dataclass, field
from typing import Protocol, runtime_checkable

from project_t_contracts import (
    AnalyzeResponse,
    ContentType,
    ContextCompressRequest,
    ContextSelectResponse,
    LogCompressRequest,
    OptimizationAppliedSummary,
    OptimizationMode,
    OptimizationRequestWire,
    OptimizationResultWire,
    OptimizationStatus,
    TokenSummary,
    ValidationSummary,
)

from ..classifier import ClassificationResult, ContentClassifier
from ..compression import compact_whitespace, compress_prose_rules, compress_terminal_output
from ..constraints import (
    ConstraintAnalysis,
    ConstraintExtractor,
    mask_protected_spans,
    unmask_protected_spans,
)
from ..context_selection import ContextDocument, ContextSelector
from ..deduplication import deduplicate_context_items, deduplicate_exact_blocks
from ..tokenization import TokenEstimator, calculate_savings_percentage
from ..validation import QualityValidator


@runtime_checkable
class SemanticCompressorProtocol(Protocol):
    """Optional AI-assisted semantic compression hook (disabled by default)."""

    def compress(
        self,
        text: str,
        *,
        content_type: ContentType,
        mode: OptimizationMode,
    ) -> str:
        ...


@dataclass(frozen=True, slots=True)
class PipelineConfig:
    """Policy and threshold defaults governing pipeline execution."""

    min_meaningful_savings_tokens: int = 1
    allow_ai_semantic_compression: bool = False
    min_tokens_for_ai_compression: int = 400


@dataclass(frozen=True, slots=True)
class PipelineTraceStep:
    """Reversible transformation trace entry emitted by orchestrator."""

    method: str
    applied: bool
    before_chars: int
    after_chars: int
    detail: str = ""


@dataclass(frozen=True, slots=True)
class OptimizationExecution:
    """Full execution record pairing wire result with status and trace steps."""

    result: OptimizationResultWire
    status: OptimizationStatus
    classification: ClassificationResult
    analysis: ConstraintAnalysis
    trace: tuple[PipelineTraceStep, ...] = field(default_factory=tuple)


class PipelineOrchestrator:
    """
    Coordinates the deterministic-first hybrid pipeline (ADR-0006 & Section 6.2).

    Guarantees automatic rollback to unmodified original input whenever validation fails,
    net token savings are zero/below threshold, or an unexpected error occurs.
    """

    def __init__(
        self,
        *,
        token_estimator: TokenEstimator | None = None,
        classifier: ContentClassifier | None = None,
        constraint_extractor: ConstraintExtractor | None = None,
        validator: QualityValidator | None = None,
        context_selector: ContextSelector | None = None,
        semantic_compressor: SemanticCompressorProtocol | None = None,
        config: PipelineConfig | None = None,
    ) -> None:
        self._estimator = token_estimator if token_estimator is not None else TokenEstimator()
        self._classifier = classifier if classifier is not None else ContentClassifier()
        self._extractor = constraint_extractor if constraint_extractor is not None else ConstraintExtractor()
        self._validator = validator if validator is not None else QualityValidator()
        self._selector = context_selector if context_selector is not None else ContextSelector(self._estimator)
        self._semantic = semantic_compressor
        self._config = config if config is not None else PipelineConfig()

    def analyze(
        self,
        *,
        content: str,
        content_type: ContentType | None = None,
        model: str = "generic",
    ) -> AnalyzeResponse:
        classification = self._classifier.classify(content, hint=content_type)
        analysis = self._extractor.extract(content)
        token_estimate = self._estimator.count(content, model=model)
        return AnalyzeResponse(
            classification=classification.to_contract(),
            constraints=analysis.constraints,
            protected_spans=list(analysis.protected_spans),
            token_estimate=token_estimate,
        )

    def optimize(self, request: OptimizationRequestWire) -> OptimizationExecution:
        started = time.perf_counter()
        request_id = f"req_{uuid.uuid4().hex[:12]}"
        original = request.content
        mode = OptimizationMode(request.mode)
        flags = request.optimization

        # Stages 1-3: Classify, baseline tokens, extract constraints & protected spans
        classification = self._classifier.classify(original, hint=request.content_type)
        content_type = classification.mapped_content_type
        baseline_tokens = self._estimator.count(original, model=request.model)
        analysis = self._extractor.extract(original)

        trace: list[PipelineTraceStep] = []
        methods: list[str] = []
        warnings: list[str] = []
        candidate = original

        try:
            # Stage 4: Exact deduplication (first canonical occurrence always retained;
            # QualityValidator re-verifies all constraints & protected spans post-pass)
            if flags.deduplicate:
                before_len = len(candidate)
                dedup_res = deduplicate_exact_blocks(
                    candidate,
                    content_type=content_type,
                )
                if dedup_res.applied:
                    candidate = dedup_res.text
                    methods.append("exact_deduplication")
                trace.append(
                    PipelineTraceStep(
                        method="exact_deduplication",
                        applied=dedup_res.applied,
                        before_chars=before_len,
                        after_chars=len(candidate),
                        detail=f"removed_blocks={dedup_res.removed_blocks}",
                    )
                )

            # Stage 5: Safe deterministic rules (terminal log extraction OR masked prose rules + whitespace)
            if content_type == ContentType.TERMINAL_OUTPUT:
                before_len = len(candidate)
                term_res = compress_terminal_output(candidate)
                if term_res.applied:
                    candidate = term_res.compressed_text
                    methods.append("terminal_log_filtering")
                trace.append(
                    PipelineTraceStep(
                        method="terminal_log_filtering",
                        applied=term_res.applied,
                        before_chars=before_len,
                        after_chars=len(candidate),
                        detail=f"omitted_lines={term_res.omitted_line_count}",
                    )
                )
            else:
                # Re-extract protected spans against current candidate before masking
                current_analysis = self._extractor.extract(candidate)
                spans_to_lock = current_analysis.protected_spans
                if not flags.preserve_identifiers:
                    spans_to_lock = tuple(
                        s
                        for s in current_analysis.protected_spans
                        if s.category in {"explicit_constraint", "output_format", "json_key_or_schema"}
                    )
                masked = mask_protected_spans(candidate, spans_to_lock)
                before_len = len(candidate)
                rewritten_masked, rules_applied = compress_prose_rules(
                    masked.masked_text,
                    content_type=content_type,
                    mode=mode,
                )
                unmasked, intact = unmask_protected_spans(rewritten_masked, masked.token_map)
                if not intact:
                    raise RuntimeError("Protected span sentinel integrity failure during rule compression")
                rule_actually_changed = rules_applied and unmasked != candidate
                if rule_actually_changed:
                    candidate = unmasked
                    methods.append("rule_based_compression")
                trace.append(
                    PipelineTraceStep(
                        method="rule_based_compression",
                        applied=rule_actually_changed,
                        before_chars=before_len,
                        after_chars=len(candidate),
                    )
                )

            before_ws = len(candidate)
            ws_candidate, ws_applied = compact_whitespace(
                candidate,
                content_type=content_type,
                mode=mode,
            )
            if ws_applied:
                candidate = ws_candidate
                methods.append("whitespace_normalization")
            trace.append(
                PipelineTraceStep(
                    method="whitespace_normalization",
                    applied=ws_applied,
                    before_chars=before_ws,
                    after_chars=len(candidate),
                )
            )

            # Stage 7: Optional AI-assisted semantic compression (strictly opt-in & gated)
            if (
                self._config.allow_ai_semantic_compression
                and flags.semantic_compression
                and mode != OptimizationMode.SAFE
                and self._semantic is not None
                and baseline_tokens.count >= self._config.min_tokens_for_ai_compression
            ):
                current_analysis = self._extractor.extract(candidate)
                masked = mask_protected_spans(candidate, current_analysis.protected_spans)
                before_ai = len(candidate)
                ai_masked = self._semantic.compress(
                    masked.masked_text,
                    content_type=content_type,
                    mode=mode,
                )
                ai_unmasked, intact = unmask_protected_spans(ai_masked, masked.token_map)
                if intact and ai_unmasked and len(ai_unmasked) < len(candidate):
                    candidate = ai_unmasked
                    methods.append("semantic_compression")
                trace.append(
                    PipelineTraceStep(
                        method="semantic_compression",
                        applied=candidate == ai_unmasked and intact,
                        before_chars=before_ai,
                        after_chars=len(candidate),
                    )
                )

            # Stage 9: Hard Quality Validation
            val_report = self._validator.validate(
                original=original,
                candidate=candidate,
                content_type=content_type,
                analysis=analysis,
                preserve_identifiers=flags.preserve_identifiers,
            )

            if not val_report.summary.passed:
                warnings.append("fallback_validation_failed")
                warnings.extend(val_report.failure_reasons)
                return self._build_fallback_execution(
                    request_id=request_id,
                    original=original,
                    baseline_tokens=baseline_tokens.count,
                    accuracy=baseline_tokens.accuracy,
                    mode=mode,
                    validation=val_report.summary,
                    status=OptimizationStatus.FALLBACK_VALIDATION_FAILED,
                    classification=classification,
                    analysis=analysis,
                    warnings=warnings,
                    started=started,
                    trace=trace,
                )

            # Stage 10: Measure candidate tokens & enforce meaningful positive savings
            candidate_tokens = self._estimator.count(candidate, model=request.model)
            tokens_saved = baseline_tokens.count - candidate_tokens.count

            if candidate == original or tokens_saved < self._config.min_meaningful_savings_tokens or tokens_saved <= 0:
                warnings.append("fallback_no_meaningful_savings")
                return self._build_fallback_execution(
                    request_id=request_id,
                    original=original,
                    baseline_tokens=baseline_tokens.count,
                    accuracy=baseline_tokens.accuracy,
                    mode=mode,
                    validation=ValidationSummary(
                        passed=True,
                        constraints_preserved=val_report.summary.constraints_preserved,
                        identifiers_preserved=val_report.summary.identifiers_preserved,
                        structure_preserved=val_report.summary.structure_preserved,
                        quality_score=1.0,
                    ),
                    status=OptimizationStatus.FALLBACK_NO_SAVINGS,
                    classification=classification,
                    analysis=analysis,
                    warnings=warnings,
                    started=started,
                    trace=trace,
                )

            reduction_pct = calculate_savings_percentage(baseline_tokens.count, candidate_tokens.count)
            duration_ms = max(0, round((time.perf_counter() - started) * 1000))
            result = OptimizationResultWire(
                request_id=request_id,
                original_content=original,
                optimized_content=candidate,
                tokens=TokenSummary(
                    original=baseline_tokens.count,
                    optimized=candidate_tokens.count,
                    saved=tokens_saved,
                    reduction_percentage=reduction_pct,
                    accuracy=candidate_tokens.accuracy,
                ),
                validation=val_report.summary,
                optimization=OptimizationAppliedSummary(methods=methods, mode=mode),
                duration_ms=duration_ms,
                warnings=warnings,
            )
            return OptimizationExecution(
                result=result,
                status=OptimizationStatus.VALIDATED,
                classification=classification,
                analysis=analysis,
                trace=tuple(trace),
            )

        except Exception:
            warnings.append("fallback_internal_error")
            return self._build_fallback_execution(
                request_id=request_id,
                original=original,
                baseline_tokens=baseline_tokens.count,
                accuracy=baseline_tokens.accuracy,
                mode=mode,
                validation=ValidationSummary(
                    passed=False,
                    constraints_preserved=True,
                    identifiers_preserved=True,
                    structure_preserved=True,
                    quality_score=1.0,
                ),
                status=OptimizationStatus.FALLBACK_ERROR,
                classification=classification,
                analysis=analysis,
                warnings=warnings,
                started=started,
                trace=trace,
            )

    def compress_logs(self, request: LogCompressRequest) -> OptimizationExecution:
        """Compress terminal/runner logs using LogCompressRequest parameters."""
        started = time.perf_counter()
        request_id = f"req_{uuid.uuid4().hex[:12]}"
        original = request.output
        classification = self._classifier.classify(original, hint=ContentType.TERMINAL_OUTPUT)
        analysis = self._extractor.extract(original)
        baseline_tokens = self._estimator.count(original, model=request.model)

        term_res = compress_terminal_output(
            original,
            command=request.command,
            exit_code=request.exit_code,
            context_lines=request.context_lines,
        )
        candidate = term_res.compressed_text
        candidate_tokens = self._estimator.count(candidate, model=request.model)
        tokens_saved = baseline_tokens.count - candidate_tokens.count

        if not term_res.applied or tokens_saved <= 0:
            return self._build_fallback_execution(
                request_id=request_id,
                original=original,
                baseline_tokens=baseline_tokens.count,
                accuracy=baseline_tokens.accuracy,
                mode=OptimizationMode.SAFE,
                validation=ValidationSummary(
                    passed=True,
                    constraints_preserved=True,
                    identifiers_preserved=True,
                    structure_preserved=True,
                    quality_score=1.0,
                ),
                status=OptimizationStatus.FALLBACK_NO_SAVINGS,
                classification=classification,
                analysis=analysis,
                warnings=["fallback_no_meaningful_savings"],
                started=started,
                trace=[],
            )

        duration_ms = max(0, round((time.perf_counter() - started) * 1000))
        result = OptimizationResultWire(
            request_id=request_id,
            original_content=original,
            optimized_content=candidate,
            tokens=TokenSummary(
                original=baseline_tokens.count,
                optimized=candidate_tokens.count,
                saved=tokens_saved,
                reduction_percentage=calculate_savings_percentage(
                    baseline_tokens.count, candidate_tokens.count
                ),
                accuracy=candidate_tokens.accuracy,
            ),
            validation=ValidationSummary(
                passed=True,
                constraints_preserved=True,
                identifiers_preserved=True,
                structure_preserved=True,
                quality_score=1.0,
            ),
            optimization=OptimizationAppliedSummary(
                methods=["terminal_log_filtering"],
                mode=OptimizationMode.SAFE,
            ),
            duration_ms=duration_ms,
            warnings=[],
        )
        return OptimizationExecution(
            result=result,
            status=OptimizationStatus.VALIDATED,
            classification=classification,
            analysis=analysis,
        )

    def compress_context_items(self, request: ContextCompressRequest) -> OptimizationExecution:
        """Deduplicate and optimize multi-part context items preserving pinned items."""
        raw_joined = "\n\n".join(item.content for item in request.items)
        item_dicts = [
            {
                "id": item.id,
                "content": item.content,
                "pinned": item.pinned,
            }
            for item in request.items
        ]
        deduped = deduplicate_context_items(item_dicts, project_id=request.project_id)
        joined_deduped = "\n\n".join(str(item["content"]) for item in deduped.kept_items)

        exec_res = self.optimize(
            OptimizationRequestWire(
                content=joined_deduped if deduped.applied else raw_joined,
                content_type=ContentType.DOCUMENTATION,
                provider=request.provider,
                model=request.model,
                mode=request.mode,
            )
        )
        # Ensure original_content always reflects full original multi-item payload
        if deduped.applied:
            orig_tokens = self._estimator.count(raw_joined, model=request.model)
            opt_tokens = exec_res.result.tokens.optimized
            saved = orig_tokens.count - opt_tokens
            if saved > 0:
                methods = ["context_item_deduplication", *exec_res.result.optimization.methods]
                updated_res = OptimizationResultWire(
                    request_id=exec_res.result.request_id,
                    original_content=raw_joined,
                    optimized_content=exec_res.result.optimized_content,
                    tokens=TokenSummary(
                        original=orig_tokens.count,
                        optimized=opt_tokens,
                        saved=saved,
                        reduction_percentage=calculate_savings_percentage(orig_tokens.count, opt_tokens),
                        accuracy=orig_tokens.accuracy,
                    ),
                    validation=exec_res.result.validation,
                    optimization=OptimizationAppliedSummary(
                        methods=list(dict.fromkeys(methods)),
                        mode=OptimizationMode(request.mode),
                    ),
                    duration_ms=exec_res.result.duration_ms,
                    warnings=exec_res.result.warnings,
                )
                return OptimizationExecution(
                    result=updated_res,
                    status=OptimizationStatus.VALIDATED,
                    classification=exec_res.classification,
                    analysis=exec_res.analysis,
                    trace=exec_res.trace,
                )
        return exec_res

    def select_context(
        self,
        *,
        task_description: str,
        documents: list[ContextDocument],
        pinned_files: list[str] | tuple[str, ...] = (),
        max_files: int = 15,
        max_tokens: int = 8000,
        model: str = "generic",
    ) -> ContextSelectResponse:
        outcome = self._selector.select(
            task_description=task_description,
            documents=documents,
            pinned_files=pinned_files,
            max_files=max_files,
            max_tokens=max_tokens,
            model=model,
        )
        return ContextSelectResponse(
            selected_files=list(outcome.selected_files),
            total_tokens=outcome.total_tokens,
            accuracy=outcome.accuracy,
            warnings=list(outcome.warnings),
        )

    def _build_fallback_execution(
        self,
        *,
        request_id: str,
        original: str,
        baseline_tokens: int,
        accuracy: str,
        mode: OptimizationMode,
        validation: ValidationSummary,
        status: OptimizationStatus,
        classification: ClassificationResult,
        analysis: ConstraintAnalysis,
        warnings: list[str],
        started: float,
        trace: list[PipelineTraceStep],
    ) -> OptimizationExecution:
        duration_ms = max(0, round((time.perf_counter() - started) * 1000))
        result = OptimizationResultWire(
            request_id=request_id,
            original_content=original,
            optimized_content=original,
            tokens=TokenSummary(
                original=baseline_tokens,
                optimized=baseline_tokens,
                saved=0,
                reduction_percentage=0.0,
                accuracy=accuracy,  # type: ignore[arg-type]
            ),
            validation=validation,
            optimization=OptimizationAppliedSummary(methods=[], mode=mode),
            duration_ms=duration_ms,
            warnings=list(dict.fromkeys(warnings)),
        )
        return OptimizationExecution(
            result=result,
            status=status,
            classification=classification,
            analysis=analysis,
            trace=tuple(trace),
        )
