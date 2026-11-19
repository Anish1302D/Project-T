"""Pydantic v2 contracts matching canonical JSON Schema & OpenAPI v1 specifications."""

from __future__ import annotations

from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field, model_validator

from .enums import (
    AccuracyLevel,
    ContentType,
    IntegrationSource,
    OptimizationMode,
)


class StrictWireModel(BaseModel):
    """Base model forbidding unexpected fields for strict wire validation."""

    model_config = ConfigDict(extra="forbid", use_enum_values=True)


class OpenWireModel(BaseModel):
    """Base model for extensible payload structures."""

    model_config = ConfigDict(extra="ignore", use_enum_values=True)


class OptimizationFlags(StrictWireModel):
    deduplicate: bool = True
    semantic_compression: bool = False
    context_filtering: bool = True
    preserve_identifiers: bool = True


class OptimizationRequestWire(StrictWireModel):
    content: str = Field(min_length=1)
    content_type: ContentType | None = None
    provider: str = "local"
    model: str = "generic"
    mode: OptimizationMode = OptimizationMode.BALANCED
    integration: IntegrationSource = IntegrationSource.API
    project_id: str | None = None
    optimization: OptimizationFlags = Field(default_factory=OptimizationFlags)


class TokenSummary(StrictWireModel):
    original: int = Field(ge=0)
    optimized: int = Field(ge=0)
    saved: int
    reduction_percentage: float
    accuracy: AccuracyLevel


class ValidationSummary(StrictWireModel):
    passed: bool
    constraints_preserved: bool
    identifiers_preserved: bool
    structure_preserved: bool = True
    quality_score: float | None = Field(default=None, ge=0.0, le=1.0)


class OptimizationAppliedSummary(StrictWireModel):
    methods: list[str]
    mode: OptimizationMode


class OptimizationResultWire(StrictWireModel):
    request_id: str = Field(min_length=1)
    original_content: str
    optimized_content: str
    tokens: TokenSummary
    validation: ValidationSummary
    optimization: OptimizationAppliedSummary
    duration_ms: int = Field(ge=0)
    warnings: list[str]


class TokenCountRequest(StrictWireModel):
    text: str | None = None
    request_payload: dict[str, Any] | None = None
    provider: str = Field(min_length=1)
    model: str = Field(min_length=1)
    allow_remote_count: bool = False

    @model_validator(mode="after")
    def _ensure_text_or_payload(self) -> TokenCountRequest:
        if self.text is None and self.request_payload is None:
            raise ValueError("Either 'text' or 'request_payload' must be provided.")
        return self


class TokenCountResult(StrictWireModel):
    count: int = Field(ge=0)
    accuracy: AccuracyLevel
    model: str = Field(min_length=1)
    provider: str = Field(min_length=1)


class ContentClassification(StrictWireModel):
    type: str
    mapped_content_type: ContentType
    language: str
    contains_code: bool
    contains_constraints: bool


class ExtractedConstraints(StrictWireModel):
    objectives: list[str]
    targets: list[str]
    constraints: list[str]


class ProtectedSpan(StrictWireModel):
    category: str
    value: str
    start: int = Field(ge=0)
    end: int = Field(ge=0)


class AnalyzeRequest(StrictWireModel):
    content: str = Field(min_length=1)
    content_type: ContentType | None = None
    provider: str = "local"
    model: str = "generic"


class AnalyzeResponse(StrictWireModel):
    classification: ContentClassification
    constraints: ExtractedConstraints
    protected_spans: list[ProtectedSpan]
    token_estimate: TokenCountResult


class ContextSelectRequest(StrictWireModel):
    task_description: str = Field(min_length=1)
    workspace_root: str = Field(min_length=1)
    pinned_files: list[str] = Field(default_factory=list)
    max_files: int = Field(default=15, ge=1, le=100)
    max_tokens: int = Field(default=8000, ge=100)
    provider: str = "local"
    model: str = "generic"


class SelectedContextFile(StrictWireModel):
    relative_path: str
    score: float
    reason: str
    estimated_tokens: int = Field(ge=0)
    pinned: bool


class ContextSelectResponse(StrictWireModel):
    selected_files: list[SelectedContextFile]
    total_tokens: int = Field(ge=0)
    accuracy: AccuracyLevel
    warnings: list[str]


class ContextItem(StrictWireModel):
    id: str = Field(min_length=1)
    content: str
    content_type: ContentType | None = None
    pinned: bool = False


class ContextCompressRequest(StrictWireModel):
    items: list[ContextItem] = Field(min_length=1)
    mode: OptimizationMode = OptimizationMode.BALANCED
    provider: str = "local"
    model: str = "generic"
    project_id: str | None = None


class LogCompressRequest(StrictWireModel):
    command: str | None = None
    exit_code: int | None = None
    output: str = Field(min_length=1)
    context_lines: int = Field(default=5, ge=0, le=50)
    provider: str = "local"
    model: str = "generic"


class HealthResponse(StrictWireModel):
    status: Literal["ok", "degraded"]
    version: str
    engine_ready: bool
    sqlite_ready: bool


class MetricsSummaryResponse(StrictWireModel):
    total_runs: int = Field(ge=0)
    total_original_tokens: int = Field(ge=0)
    total_optimized_tokens: int = Field(ge=0)
    total_tokens_saved: int
    median_reduction_percentage: float | None = None
    fallback_count: int = Field(ge=0)
    by_accuracy: dict[str, int] = Field(default_factory=dict)


class RuntimeSettings(StrictWireModel):
    default_mode: OptimizationMode = OptimizationMode.BALANCED
    preserve_identifiers: bool = True
    allow_ai_semantic_compression: bool = False
    allow_remote_token_counting: bool = False
    cloud_sync_enabled: bool = False
    store_raw_history_locally: bool = False
    local_retention_days: int = Field(default=30, ge=1, le=365)


class RuntimeSettingsUpdate(StrictWireModel):
    default_mode: OptimizationMode | None = None
    preserve_identifiers: bool | None = None
    allow_ai_semantic_compression: bool | None = None
    allow_remote_token_counting: bool | None = None
    cloud_sync_enabled: bool | None = None
    store_raw_history_locally: bool | None = None
    local_retention_days: int | None = Field(default=None, ge=1, le=365)


class ProviderModelInfo(StrictWireModel):
    model_name: str
    supports_exact_local_count: bool
    pricing_version: str


class ProviderCatalogEntry(StrictWireModel):
    id: str
    display_name: str
    models: list[ProviderModelInfo]


class ProvidersResponse(StrictWireModel):
    providers: list[ProviderCatalogEntry]


class ErrorDetail(StrictWireModel):
    code: str
    message: str
    request_id: str | None = None


class ErrorResponse(StrictWireModel):
    error: ErrorDetail
