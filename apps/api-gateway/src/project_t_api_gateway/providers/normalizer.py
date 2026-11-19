"""Normalized provider request optimizer with fail-open original fallback."""

from __future__ import annotations

import time
import uuid
from dataclasses import dataclass, field
from typing import Any

from project_t_contracts import (
    AccuracyLevel,
    ContentType,
    OptimizationAppliedSummary,
    OptimizationFlags,
    OptimizationMode,
    OptimizationRequestWire,
    OptimizationResultWire,
    OptimizationStatus,
    TokenSummary,
    ValidationSummary,
)
from project_t_optimization_core import (
    PipelineOrchestrator,
    TokenEstimator,
    calculate_savings_percentage,
)
from project_t_provider_adapters import (
    ProviderRegistry,
    optimize_anthropic_payload,
    optimize_google_payload,
    optimize_openai_chat_payload,
)

from ..middleware import verify_provider_payload_invariance


@dataclass(frozen=True, slots=True)
class GatewayOptimizationOutcome:
    """Outcome of optimizing an incoming provider API payload."""

    request_id: str
    provider: str
    model: str
    payload_to_forward: dict[str, Any]
    gateway_status: str  # "optimized" | "bypassed" | "fallback" | "unchanged"
    optimization_status: OptimizationStatus
    original_tokens: int
    optimized_tokens: int
    tokens_saved: int
    accuracy: AccuracyLevel
    mode: OptimizationMode
    methods: tuple[str, ...] = field(default_factory=tuple)
    warnings: tuple[str, ...] = field(default_factory=tuple)
    duration_ms: int = 0

    def to_wire_summary(self) -> OptimizationResultWire:
        return OptimizationResultWire(
            request_id=self.request_id,
            original_content="[redacted_gateway_payload]",
            optimized_content="[redacted_gateway_payload]",
            tokens=TokenSummary(
                original=self.original_tokens,
                optimized=self.optimized_tokens,
                saved=self.tokens_saved,
                reduction_percentage=calculate_savings_percentage(
                    self.original_tokens, self.optimized_tokens
                ),
                accuracy=self.accuracy,
            ),
            validation=ValidationSummary(
                passed=self.optimization_status != OptimizationStatus.FALLBACK_VALIDATION_FAILED,
                constraints_preserved=True,
                identifiers_preserved=True,
                structure_preserved=True,
            ),
            optimization=OptimizationAppliedSummary(
                methods=list(self.methods),
                mode=self.mode,
            ),
            duration_ms=self.duration_ms,
            warnings=list(self.warnings),
        )


class GatewayOptimizer:
    """Optimizes eligible prompt/message text blocks while guaranteeing fail-open forwarding."""

    def __init__(self, registry: ProviderRegistry) -> None:
        self._registry = registry

    def process(
        self,
        *,
        provider: str,
        model: str,
        payload: dict[str, Any],
        mode: OptimizationMode = OptimizationMode.BALANCED,
        bypass: bool = False,
    ) -> GatewayOptimizationOutcome:
        started = time.perf_counter()
        request_id = f"gw_{uuid.uuid4().hex[:12]}"
        adapter = self._registry.resolve_tokenizer(provider)
        estimator = TokenEstimator(adapter=adapter)
        orchestrator = PipelineOrchestrator(token_estimator=estimator)

        if bypass:
            baseline_only = self._count_payload_text_tokens(provider, payload, estimator, model)
            return GatewayOptimizationOutcome(
                request_id=request_id,
                provider=provider,
                model=model,
                payload_to_forward=payload,
                gateway_status="bypassed",
                optimization_status=OptimizationStatus.FALLBACK_NO_SAVINGS,
                original_tokens=baseline_only.count,
                optimized_tokens=baseline_only.count,
                tokens_saved=0,
                accuracy=baseline_only.accuracy,
                mode=mode,
                warnings=("gateway_bypass_enabled",),
                duration_ms=max(0, round((time.perf_counter() - started) * 1000)),
            )

        collected_methods: list[str] = []
        collected_warnings: list[str] = []
        accuracies: set[AccuracyLevel] = set()

        # Respect JSON-mode structured output contracts strictly: if response_format/responseSchema
        # requests JSON, preserve JSON payloads verbatim (safe mode)
        has_json_contract = bool(payload.get("response_format")) or bool(
            isinstance(payload.get("generationConfig"), dict)
            and (
                payload["generationConfig"].get("responseSchema")
                or payload["generationConfig"].get("responseMimeType") == "application/json"
            )
        )
        effective_mode = OptimizationMode.SAFE if has_json_contract else mode

        def _optimize_segment(text: str, hint: ContentType | None) -> tuple[str, int, int]:
            exec_res = orchestrator.optimize(
                OptimizationRequestWire(
                    content=text,
                    content_type=hint,
                    provider=provider,
                    model=model,
                    mode=effective_mode,
                    integration="gateway",
                    optimization=OptimizationFlags(
                        deduplicate=True,
                        semantic_compression=False,
                        context_filtering=True,
                        preserve_identifiers=True,
                    ),
                )
            )
            res = exec_res.result
            accuracies.add(AccuracyLevel(res.tokens.accuracy))
            collected_methods.extend(res.optimization.methods)
            collected_warnings.extend(res.warnings)
            return res.optimized_content, res.tokens.original, res.tokens.optimized

        try:
            if provider == "openai":
                candidate, orig_tok, opt_tok = optimize_openai_chat_payload(payload, _optimize_segment)
            elif provider == "anthropic":
                candidate, orig_tok, opt_tok = optimize_anthropic_payload(payload, _optimize_segment)
            elif provider == "google":
                candidate, orig_tok, opt_tok = optimize_google_payload(payload, _optimize_segment)
            else:
                raise ValueError(f"Unsupported gateway provider '{provider}'")

            invariant_ok, violation = verify_provider_payload_invariance(provider, payload, candidate)
            if not invariant_ok:
                collected_warnings.append(violation or "invariance_check_failed")
                return GatewayOptimizationOutcome(
                    request_id=request_id,
                    provider=provider,
                    model=model,
                    payload_to_forward=payload,
                    gateway_status="fallback",
                    optimization_status=OptimizationStatus.FALLBACK_VALIDATION_FAILED,
                    original_tokens=orig_tok,
                    optimized_tokens=orig_tok,
                    tokens_saved=0,
                    accuracy=(
                        AccuracyLevel.EXACT
                        if accuracies == {AccuracyLevel.EXACT}
                        else AccuracyLevel.ESTIMATED
                    ),
                    mode=effective_mode,
                    warnings=tuple(dict.fromkeys(collected_warnings)),
                    duration_ms=max(0, round((time.perf_counter() - started) * 1000)),
                )

            saved = max(0, orig_tok - opt_tok)
            overall_accuracy = (
                AccuracyLevel.EXACT
                if accuracies == {AccuracyLevel.EXACT}
                else AccuracyLevel.ESTIMATED
            )
            if saved <= 0 or candidate == payload:
                return GatewayOptimizationOutcome(
                    request_id=request_id,
                    provider=provider,
                    model=model,
                    payload_to_forward=payload,
                    gateway_status="unchanged",
                    optimization_status=OptimizationStatus.FALLBACK_NO_SAVINGS,
                    original_tokens=orig_tok,
                    optimized_tokens=orig_tok,
                    tokens_saved=0,
                    accuracy=overall_accuracy,
                    mode=effective_mode,
                    warnings=tuple(dict.fromkeys(collected_warnings)),
                    duration_ms=max(0, round((time.perf_counter() - started) * 1000)),
                )

            return GatewayOptimizationOutcome(
                request_id=request_id,
                provider=provider,
                model=model,
                payload_to_forward=candidate,
                gateway_status="optimized",
                optimization_status=OptimizationStatus.VALIDATED,
                original_tokens=orig_tok,
                optimized_tokens=opt_tok,
                tokens_saved=saved,
                accuracy=overall_accuracy,
                mode=effective_mode,
                methods=tuple(dict.fromkeys(collected_methods)),
                warnings=tuple(dict.fromkeys(collected_warnings)),
                duration_ms=max(0, round((time.perf_counter() - started) * 1000)),
            )
        except Exception:
            return GatewayOptimizationOutcome(
                request_id=request_id,
                provider=provider,
                model=model,
                payload_to_forward=payload,
                gateway_status="fallback",
                optimization_status=OptimizationStatus.FALLBACK_ERROR,
                original_tokens=0,
                optimized_tokens=0,
                tokens_saved=0,
                accuracy=AccuracyLevel.ESTIMATED,
                mode=mode,
                warnings=("gateway_optimization_error_fail_open",),
                duration_ms=max(0, round((time.perf_counter() - started) * 1000)),
            )

    def _count_payload_text_tokens(
        self,
        provider: str,
        payload: dict[str, Any],
        estimator: TokenEstimator,
        model: str,
    ):
        total = 0
        accuracies: set[AccuracyLevel] = set()

        def _count_only(text: str, _hint: ContentType | None) -> tuple[str, int, int]:
            res = estimator.count(text, model=model)
            nonlocal total
            total += res.count
            accuracies.add(AccuracyLevel(res.accuracy))
            return text, res.count, res.count

        if provider == "openai":
            optimize_openai_chat_payload(payload, _count_only)
        elif provider == "anthropic":
            optimize_anthropic_payload(payload, _count_only)
        elif provider == "google":
            optimize_google_payload(payload, _count_only)

        acc = AccuracyLevel.EXACT if accuracies == {AccuracyLevel.EXACT} else AccuracyLevel.ESTIMATED
        from project_t_contracts import TokenCountResult

        return TokenCountResult(count=total, accuracy=acc, model=model, provider=provider)
