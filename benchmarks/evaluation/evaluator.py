"""Reproducible benchmark evaluator across core optimization engine categories."""

from __future__ import annotations

import json
import os
import platform
import statistics
import time
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Any

from project_t_contracts import (
    ContentType,
    LogCompressRequest,
    OptimizationMode,
    OptimizationRequestWire,
    OptimizationStatus,
)
from project_t_optimization_core import ContextDocument, PipelineOrchestrator, TokenEstimator
from project_t_provider_adapters import ProviderRegistry


@dataclass(frozen=True, slots=True)
class HardwareEnvironment:
    os_platform: str
    machine: str
    processor: str
    cpu_count: int | None
    python_version: str


@dataclass(frozen=True, slots=True)
class CaseEvaluation:
    case_id: str
    category: str
    eligible: bool
    original_tokens: int
    optimized_tokens: int
    tokens_saved: int
    reduction_percentage: float
    accuracy: str
    status: str
    latency_ms: float
    constraints_ok: bool
    identifiers_ok: bool
    structure_ok: bool
    assertions_ok: bool
    methods: tuple[str, ...] = field(default_factory=tuple)
    warnings: tuple[str, ...] = field(default_factory=tuple)


@dataclass(frozen=True, slots=True)
class CategorySummary:
    category: str
    sample_count: int
    eligible_count: int
    validated_count: int
    fallback_count: int
    negative_or_zero_savings_count: int
    assertion_pass_rate: float
    constraint_preservation_rate: float
    identifier_preservation_rate: float
    structure_pass_rate: float
    median_reduction_pct_all: float
    median_reduction_pct_eligible: float
    p10_reduction_pct: float
    p90_reduction_pct: float
    p50_latency_ms: float
    p95_latency_ms: float


def _percentile(sorted_values: list[float], pct: float) -> float:
    if not sorted_values:
        return 0.0
    if len(sorted_values) == 1:
        return round(sorted_values[0], 2)
    idx = (len(sorted_values) - 1) * (pct / 100.0)
    lo = int(idx)
    hi = min(lo + 1, len(sorted_values) - 1)
    frac = idx - lo
    return round(sorted_values[lo] * (1 - frac) + sorted_values[hi] * frac, 2)


def _load_jsonl(path: Path) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for raw_line in path.read_text(encoding="utf-8").splitlines():
        line = raw_line.strip()
        if line:
            rows.append(json.loads(line))
    return rows


def capture_hardware_env() -> HardwareEnvironment:
    return HardwareEnvironment(
        os_platform=platform.platform(),
        machine=platform.machine(),
        processor=platform.processor() or "unknown",
        cpu_count=os.cpu_count(),
        python_version=platform.python_version(),
    )


class BenchmarkEvaluator:
    """Runs deterministic benchmark datasets against PipelineOrchestrator."""

    def __init__(
        self,
        *,
        datasets_dir: Path,
        provider: str = "openai",
        model: str = "gpt-4o",
        default_mode: OptimizationMode = OptimizationMode.BALANCED,
    ) -> None:
        self._datasets_dir = datasets_dir
        self._provider = provider
        self._model = model
        self._default_mode = default_mode
        adapter = ProviderRegistry().resolve_tokenizer(provider)
        # Warm up local tokenizer encoding once (matches persistent local-runtime daemon lifecycle)
        adapter.count_text("warmup", model)
        self._orchestrator = PipelineOrchestrator(
            token_estimator=TokenEstimator(adapter=adapter)
        )

    def run_all(self) -> dict[str, Any]:
        all_cases: list[CaseEvaluation] = []
        categories: list[CategorySummary] = []

        for cat_name, runner_fn in [
            ("prompt", self._eval_text_category),
            ("constraint", self._eval_text_category),
            ("code", self._eval_text_category),
            ("conversation", self._eval_text_category),
            ("log", self._eval_log_category),
            ("repository", self._eval_repository_category),
            ("api", self._eval_api_category),
        ]:
            dataset_path = self._datasets_dir / f"{cat_name}.jsonl"
            if not dataset_path.exists():
                continue
            rows = _load_jsonl(dataset_path)
            cases = runner_fn(cat_name, rows)
            all_cases.extend(cases)
            categories.append(self._summarize(cat_name, cases))

        latency_cases = self._eval_latency_category()
        all_cases.extend(latency_cases)
        categories.append(self._summarize("latency", latency_cases))

        return {
            "engine_version": "0.1.0",
            "dataset_version": "2026-11-v1",
            "provider": self._provider,
            "model": self._model,
            "default_mode": self._default_mode.value,
            "note": (
                "Deterministic offline/local benchmark report. Diagnostic quality_score is not proof "
                "of downstream LLM equivalence; paired LLM evaluations are tracked separately."
            ),
            "hardware": asdict(capture_hardware_env()),
            "categories": [asdict(c) for c in categories],
            "cases": [asdict(case) for case in all_cases],
        }

    def _eval_text_category(
        self,
        category: str,
        rows: list[dict[str, Any]],
    ) -> list[CaseEvaluation]:
        results: list[CaseEvaluation] = []
        for row in rows:
            mode = OptimizationMode(row.get("mode", self._default_mode.value))
            eligible = bool(row.get("eligible", True))
            content_type = (
                ContentType(row["content_type"]) if row.get("content_type") else None
            )
            t0 = time.perf_counter()
            exec_res = self._orchestrator.optimize(
                OptimizationRequestWire(
                    content=row["content"],
                    content_type=content_type,
                    provider=self._provider,
                    model=self._model,
                    mode=mode,
                )
            )
            elapsed_ms = (time.perf_counter() - t0) * 1000.0
            res = exec_res.result

            expected_subs = [
                *row.get("required_substrings", []),
                *row.get("expected_constraints", []),
                *row.get("expected_identifiers", []),
            ]
            assertions_ok = all(sub in res.optimized_content for sub in expected_subs)

            results.append(
                CaseEvaluation(
                    case_id=row["id"],
                    category=category,
                    eligible=eligible,
                    original_tokens=res.tokens.original,
                    optimized_tokens=res.tokens.optimized,
                    tokens_saved=res.tokens.saved,
                    reduction_percentage=res.tokens.reduction_percentage,
                    accuracy=res.tokens.accuracy,
                    status=exec_res.status.value,
                    latency_ms=round(elapsed_ms, 3),
                    constraints_ok=res.validation.constraints_preserved,
                    identifiers_ok=res.validation.identifiers_preserved,
                    structure_ok=res.validation.structure_preserved,
                    assertions_ok=assertions_ok,
                    methods=tuple(res.optimization.methods),
                    warnings=tuple(res.warnings),
                )
            )
        return results

    def _eval_log_category(
        self,
        category: str,
        rows: list[dict[str, Any]],
    ) -> list[CaseEvaluation]:
        results: list[CaseEvaluation] = []
        for row in rows:
            t0 = time.perf_counter()
            exec_res = self._orchestrator.compress_logs(
                LogCompressRequest(
                    command=row.get("command"),
                    exit_code=row.get("exit_code"),
                    output=row["output"],
                    provider=self._provider,
                    model=self._model,
                )
            )
            elapsed_ms = (time.perf_counter() - t0) * 1000.0
            res = exec_res.result
            assertions_ok = all(
                sub in res.optimized_content for sub in row.get("expected_substrings", [])
            )
            results.append(
                CaseEvaluation(
                    case_id=row["id"],
                    category=category,
                    eligible=True,
                    original_tokens=res.tokens.original,
                    optimized_tokens=res.tokens.optimized,
                    tokens_saved=res.tokens.saved,
                    reduction_percentage=res.tokens.reduction_percentage,
                    accuracy=res.tokens.accuracy,
                    status=exec_res.status.value,
                    latency_ms=round(elapsed_ms, 3),
                    constraints_ok=True,
                    identifiers_ok=True,
                    structure_ok=True,
                    assertions_ok=assertions_ok,
                    methods=tuple(res.optimization.methods),
                    warnings=tuple(res.warnings),
                )
            )
        return results

    def _eval_repository_category(
        self,
        category: str,
        rows: list[dict[str, Any]],
    ) -> list[CaseEvaluation]:
        results: list[CaseEvaluation] = []
        for row in rows:
            docs = [
                ContextDocument(
                    relative_path=d["relative_path"],
                    content=d["content"],
                    symbols=tuple(d.get("symbols", [])),
                    imports=tuple(d.get("imports", [])),
                    modified_epoch=float(d.get("modified_epoch", 0.0)),
                )
                for d in row["documents"]
            ]
            t0 = time.perf_counter()
            sel = self._orchestrator.select_context(
                task_description=row["task_description"],
                documents=docs,
                pinned_files=row.get("pinned_files", []),
                model=self._model,
            )
            elapsed_ms = (time.perf_counter() - t0) * 1000.0
            total_doc_tokens = sum(
                self._orchestrator._estimator.count(d.content, model=self._model).count
                for d in docs
            )
            selected_paths = {f.relative_path for f in sel.selected_files}
            expected = set(row.get("expected_relevant", []))
            assertions_ok = expected.issubset(selected_paths)
            saved = max(0, total_doc_tokens - sel.total_tokens)
            reduction = round((saved / total_doc_tokens) * 100.0, 2) if total_doc_tokens > 0 else 0.0
            results.append(
                CaseEvaluation(
                    case_id=row["id"],
                    category=category,
                    eligible=True,
                    original_tokens=total_doc_tokens,
                    optimized_tokens=sel.total_tokens,
                    tokens_saved=saved,
                    reduction_percentage=reduction,
                    accuracy=sel.accuracy,
                    status=OptimizationStatus.VALIDATED.value,
                    latency_ms=round(elapsed_ms, 3),
                    constraints_ok=True,
                    identifiers_ok=True,
                    structure_ok=True,
                    assertions_ok=assertions_ok,
                    methods=("bm25_fts5_selection",),
                    warnings=tuple(sel.warnings),
                )
            )
        return results

    def _eval_api_category(
        self,
        category: str,
        rows: list[dict[str, Any]],
    ) -> list[CaseEvaluation]:
        import tempfile

        import httpx
        from fastapi.testclient import TestClient

        from project_t_api_gateway import (
            GatewayConfig,
            create_gateway_app,
            verify_provider_payload_invariance,
        )

        # Use deterministic BPE token counter to simulate provider-confirmed input token accounting
        tokenizer = ProviderRegistry(allow_tiktoken=True).resolve_tokenizer("openai")
        sent_bodies: list[dict[str, Any]] = []

        def _counting_upstream(request: httpx.Request) -> httpx.Response:
            body = json.loads(request.content.decode("utf-8"))
            sent_bodies.append(body)
            serialized = json.dumps(body, sort_keys=True, ensure_ascii=False)
            confirmed_tokens = tokenizer.count_text(serialized, "gpt-4o").count
            url = str(request.url)
            if "/v1/chat/completions" in url:
                return httpx.Response(
                    200,
                    json={
                        "id": "bench_oai",
                        "usage": {"prompt_tokens": confirmed_tokens, "completion_tokens": 8},
                    },
                )
            if "/v1/messages" in url:
                return httpx.Response(
                    200,
                    json={
                        "id": "bench_ant",
                        "usage": {"input_tokens": confirmed_tokens, "output_tokens": 8},
                    },
                )
            return httpx.Response(
                200,
                json={
                    "candidates": [{"content": {"parts": [{"text": "ok"}]}}],
                    "usageMetadata": {"promptTokenCount": confirmed_tokens},
                },
            )

        results: list[CaseEvaluation] = []
        with tempfile.TemporaryDirectory() as tmp_dir:
            tmp_path = Path(tmp_dir)
            app = create_gateway_app(
                config=GatewayConfig(
                    data_dir=tmp_path,
                    db_path=tmp_path / "api_benchmark.db",
                    allow_tiktoken=True,
                ),
                upstream_transport=httpx.MockTransport(_counting_upstream),
            )
            with TestClient(app) as client:
                for row in rows:
                    provider = row["provider"]
                    endpoint = row["endpoint"]
                    payload = row["payload"]
                    eligible = bool(row.get("eligible", True))

                    # 1. Baseline pass-through via X-ProjectT-Bypass
                    base_resp = client.post(
                        endpoint,
                        json=payload,
                        headers={"X-ProjectT-Bypass": "true"},
                    )
                    base_json = base_resp.json()
                    if provider == "openai":
                        base_confirmed = int(base_json["usage"]["prompt_tokens"])
                    elif provider == "anthropic":
                        base_confirmed = int(base_json["usage"]["input_tokens"])
                    else:
                        base_confirmed = int(base_json["usageMetadata"]["promptTokenCount"])

                    # 2. Gateway-optimized paired run
                    t0 = time.perf_counter()
                    opt_resp = client.post(endpoint, json=payload)
                    elapsed_ms = (time.perf_counter() - t0) * 1000.0
                    opt_json = opt_resp.json()
                    forwarded_payload = sent_bodies[-1]

                    if provider == "openai":
                        opt_confirmed = int(opt_json["usage"]["prompt_tokens"])
                    elif provider == "anthropic":
                        opt_confirmed = int(opt_json["usage"]["input_tokens"])
                    else:
                        opt_confirmed = int(opt_json["usageMetadata"]["promptTokenCount"])

                    invariant_ok, _ = verify_provider_payload_invariance(
                        provider, payload, forwarded_payload
                    )
                    forwarded_dump = json.dumps(forwarded_payload, ensure_ascii=False)
                    expected_subs = list(row.get("required_substrings", []))
                    subs_ok = all(sub in forwarded_dump for sub in expected_subs)

                    saved = max(0, base_confirmed - opt_confirmed)
                    reduction = (
                        round((saved / base_confirmed) * 100.0, 2) if base_confirmed > 0 else 0.0
                    )
                    gw_status = opt_resp.headers.get("X-ProjectT-Status", "unchanged")
                    status = (
                        OptimizationStatus.VALIDATED.value
                        if gw_status == "optimized"
                        else OptimizationStatus.FALLBACK_NO_SAVINGS.value
                    )
                    assertions_ok = (
                        opt_resp.status_code == 200
                        and invariant_ok
                        and subs_ok
                        and (not eligible or opt_confirmed < base_confirmed)
                    )

                    results.append(
                        CaseEvaluation(
                            case_id=row["id"],
                            category=category,
                            eligible=eligible,
                            original_tokens=base_confirmed,
                            optimized_tokens=opt_confirmed,
                            tokens_saved=saved,
                            reduction_percentage=reduction,
                            accuracy="exact",
                            status=status,
                            latency_ms=round(elapsed_ms, 3),
                            constraints_ok=invariant_ok and subs_ok,
                            identifiers_ok=subs_ok,
                            structure_ok=invariant_ok,
                            assertions_ok=assertions_ok,
                            methods=(f"gateway_{provider}",),
                            warnings=(),
                        )
                    )

        return results

    def _eval_latency_category(self) -> list[CaseEvaluation]:
        small_prompt = (
            "Hello, could you please inspect `verifyJwtToken` in src/auth/jwt.py in order to "
            "fix the 401 timeout issue? Do not change the database schema."
        )
        medium_prompt = (
            small_prompt
            + "\n\n"
            + ("Repeated context paragraph explaining JWT validation workflow.\n\n" * 4)
        )
        results: list[CaseEvaluation] = []
        for idx, (label, text) in enumerate(
            [("latency_small_1", small_prompt), ("latency_small_2", small_prompt), ("latency_medium", medium_prompt)],
            start=1,
        ):
            t0 = time.perf_counter()
            exec_res = self._orchestrator.optimize(
                OptimizationRequestWire(
                    content=text,
                    provider=self._provider,
                    model=self._model,
                    mode=self._default_mode,
                )
            )
            elapsed_ms = (time.perf_counter() - t0) * 1000.0
            res = exec_res.result
            results.append(
                CaseEvaluation(
                    case_id=f"{label}_{idx}",
                    category="latency",
                    eligible=True,
                    original_tokens=res.tokens.original,
                    optimized_tokens=res.tokens.optimized,
                    tokens_saved=res.tokens.saved,
                    reduction_percentage=res.tokens.reduction_percentage,
                    accuracy=res.tokens.accuracy,
                    status=exec_res.status.value,
                    latency_ms=round(elapsed_ms, 3),
                    constraints_ok=res.validation.constraints_preserved,
                    identifiers_ok=res.validation.identifiers_preserved,
                    structure_ok=res.validation.structure_preserved,
                    assertions_ok=elapsed_ms < 100.0,
                    methods=tuple(res.optimization.methods),
                    warnings=tuple(res.warnings),
                )
            )
        return results

    def _summarize(self, category: str, cases: list[CaseEvaluation]) -> CategorySummary:
        n = len(cases)
        eligible_cases = [c for c in cases if c.eligible]
        all_reductions = sorted(c.reduction_percentage for c in cases)
        eligible_reductions = sorted(c.reduction_percentage for c in eligible_cases)
        latencies = sorted(c.latency_ms for c in cases)

        validated_count = sum(1 for c in cases if c.status == OptimizationStatus.VALIDATED.value)
        fallback_count = n - validated_count
        neg_or_zero = sum(1 for c in cases if c.tokens_saved <= 0)

        return CategorySummary(
            category=category,
            sample_count=n,
            eligible_count=len(eligible_cases),
            validated_count=validated_count,
            fallback_count=fallback_count,
            negative_or_zero_savings_count=neg_or_zero,
            assertion_pass_rate=round(sum(1 for c in cases if c.assertions_ok) / n, 4) if n else 0.0,
            constraint_preservation_rate=round(sum(1 for c in cases if c.constraints_ok) / n, 4) if n else 0.0,
            identifier_preservation_rate=round(sum(1 for c in cases if c.identifiers_ok) / n, 4) if n else 0.0,
            structure_pass_rate=round(sum(1 for c in cases if c.structure_ok) / n, 4) if n else 0.0,
            median_reduction_pct_all=round(statistics.median(all_reductions), 2) if all_reductions else 0.0,
            median_reduction_pct_eligible=round(statistics.median(eligible_reductions), 2)
            if eligible_reductions
            else 0.0,
            p10_reduction_pct=_percentile(all_reductions, 10),
            p90_reduction_pct=_percentile(all_reductions, 90),
            p50_latency_ms=round(statistics.median(latencies), 3) if latencies else 0.0,
            p95_latency_ms=_percentile(latencies, 95),
        )
