"""Strict metadata-only Pydantic schemas for cloud sync endpoints."""

from __future__ import annotations

from typing import Any, Literal

from project_t_contracts import AccuracyLevel, ContentType, IntegrationSource, OptimizationMode, OptimizationStatus
from pydantic import BaseModel, ConfigDict, Field


class StrictSyncModel(BaseModel):
    model_config = ConfigDict(extra="forbid", populate_by_name=True)


class SyncedOptimizationRun(StrictSyncModel):
    run_id: str = Field(..., min_length=1, max_length=128)
    request_id: str = Field(..., min_length=1, max_length=128)
    provider: str = Field(..., min_length=1, max_length=64)
    model: str = Field(..., min_length=1, max_length=128)
    integration: IntegrationSource
    content_type: ContentType
    optimization_mode: OptimizationMode
    status: OptimizationStatus
    methods: list[str] = Field(default_factory=list, max_length=32)
    warnings: list[str] = Field(default_factory=list, max_length=32)
    quality_score: float | None = Field(default=None, ge=0.0, le=1.0)
    duration_ms: int = Field(..., ge=0)
    original_tokens: int = Field(..., ge=0)
    optimized_tokens: int = Field(..., ge=0)
    tokens_saved: int
    reduction_percentage: float
    accuracy: AccuracyLevel
    provider_confirmed_original_tokens: int | None = Field(default=None, ge=0)
    provider_confirmed_input_tokens: int | None = Field(default=None, ge=0)
    pricing_version: str | None = Field(default=None, max_length=64)
    estimated_cost_avoided_usd: float = Field(default=0.0, ge=0.0)
    provider_confirmed_cost_avoided_usd: float | None = Field(default=None, ge=0.0)
    created_at: str | None = Field(default=None, max_length=64)


class SyncRunsRequest(StrictSyncModel):
    installation_id: str = Field(..., min_length=1, max_length=128)
    runs: list[SyncedOptimizationRun] = Field(default_factory=list, max_length=500)


class SyncRuleRequest(StrictSyncModel):
    rule_id: str = Field(..., min_length=1, max_length=128)
    installation_id: str = Field(..., min_length=1, max_length=128)
    project_id: str | None = Field(default=None, max_length=128)
    scope: Literal["global", "integration", "project"] = "global"
    mode: OptimizationMode = OptimizationMode.BALANCED
    preserve_identifiers: bool = True
    allow_ai_semantic_compression: bool = False
    min_meaningful_savings_tokens: int = Field(default=10, ge=0, le=10000)
    rules: dict[str, Any] = Field(default_factory=dict)
    version: int = Field(..., ge=1)
    prefer_local_override: bool = True


class SyncedBenchmarkResult(StrictSyncModel):
    id: str = Field(..., min_length=1, max_length=128)
    suite_name: str = Field(..., min_length=1, max_length=128)
    category: Literal[
        "prompt",
        "constraint",
        "code",
        "repository",
        "log",
        "conversation",
        "api",
        "latency",
    ]
    dataset_version: str = Field(..., min_length=1, max_length=64)
    engine_version: str = Field(..., min_length=1, max_length=64)
    provider: str = Field(default="openai", min_length=1, max_length=64)
    model: str = Field(default="gpt-4o", min_length=1, max_length=128)
    optimization_mode: OptimizationMode = OptimizationMode.BALANCED
    sample_count: int = Field(..., ge=0)
    unit_test_pass_rate: float | None = Field(default=None, ge=0.0, le=1.0)
    constraint_preservation_rate: float | None = Field(default=None, ge=0.0, le=1.0)
    identifier_preservation_rate: float | None = Field(default=None, ge=0.0, le=1.0)
    median_reduction_pct: float | None = None
    p50_latency_ms: float | None = Field(default=None, ge=0.0)
    p95_latency_ms: float | None = Field(default=None, ge=0.0)
    negative_savings_count: int = Field(default=0, ge=0)
    paired_quality_delta: float | None = None
    report_uri: str | None = Field(default=None, max_length=256)


class SyncBenchmarksRequest(StrictSyncModel):
    installation_id: str = Field(..., min_length=1, max_length=128)
    results: list[SyncedBenchmarkResult] = Field(default_factory=list, max_length=100)
