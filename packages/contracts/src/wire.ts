/**
 * Canonical wire contracts matching:
 * - packages/contracts/schemas/contracts.v1.schema.json
 * - packages/contracts/schemas/openapi-local-v1.yaml
 */

export const OPTIMIZATION_MODES = ["safe", "balanced", "aggressive"] as const;
export type OptimizationMode = (typeof OPTIMIZATION_MODES)[number];

export const CONTENT_TYPES = [
  "prompt",
  "developer_prompt",
  "source_code",
  "json",
  "documentation",
  "terminal_output",
  "conversation",
  "tool_result"
] as const;
export type ContentType = (typeof CONTENT_TYPES)[number];

export const ACCURACY_LEVELS = ["exact", "estimated"] as const;
export type AccuracyLevel = (typeof ACCURACY_LEVELS)[number];

export const INTEGRATION_SOURCES = [
  "vscode",
  "browser",
  "mcp",
  "gateway",
  "cli",
  "api"
] as const;
export type IntegrationSource = (typeof INTEGRATION_SOURCES)[number];

export const OPTIMIZATION_STATUSES = [
  "validated",
  "fallback_validation_failed",
  "fallback_no_savings",
  "fallback_error"
] as const;
export type OptimizationStatus = (typeof OPTIMIZATION_STATUSES)[number];

export interface OptimizationFlagsWire {
  deduplicate?: boolean;
  semantic_compression?: boolean;
  context_filtering?: boolean;
  preserve_identifiers?: boolean;
}

export interface OptimizationRequestWire {
  content: string;
  content_type?: ContentType;
  provider?: string;
  model?: string;
  mode?: OptimizationMode;
  integration?: IntegrationSource;
  project_id?: string;
  optimization?: OptimizationFlagsWire;
}

export interface TokenSummaryWire {
  original: number;
  optimized: number;
  saved: number;
  reduction_percentage: number;
  accuracy: AccuracyLevel;
}

export interface ValidationSummaryWire {
  passed: boolean;
  constraints_preserved: boolean;
  identifiers_preserved: boolean;
  structure_preserved?: boolean;
  quality_score?: number;
}

export interface OptimizationAppliedSummaryWire {
  methods: string[];
  mode: OptimizationMode;
}

export interface OptimizationResultWire {
  request_id: string;
  original_content: string;
  optimized_content: string;
  tokens: TokenSummaryWire;
  validation: ValidationSummaryWire;
  optimization: OptimizationAppliedSummaryWire;
  duration_ms: number;
  warnings: string[];
}

export interface TokenCountRequestWire {
  text?: string;
  request_payload?: Record<string, unknown>;
  provider: string;
  model: string;
  allow_remote_count?: boolean;
}

export interface TokenCountResultWire {
  count: number;
  accuracy: AccuracyLevel;
  model: string;
  provider: string;
}

export interface ContentClassificationWire {
  type: string;
  mapped_content_type: ContentType;
  language: string;
  contains_code: boolean;
  contains_constraints: boolean;
}

export interface ExtractedConstraintsWire {
  objectives: string[];
  targets: string[];
  constraints: string[];
}

export interface ProtectedSpanWire {
  category: string;
  value: string;
  start: number;
  end: number;
}

export interface AnalyzeRequestWire {
  content: string;
  content_type?: ContentType;
  provider?: string;
  model?: string;
}

export interface AnalyzeResponseWire {
  classification: ContentClassificationWire;
  constraints: ExtractedConstraintsWire;
  protected_spans: ProtectedSpanWire[];
  token_estimate: TokenCountResultWire;
}

export interface ContextSelectRequestWire {
  task_description: string;
  workspace_root: string;
  pinned_files?: string[];
  max_files?: number;
  max_tokens?: number;
  provider?: string;
  model?: string;
}

export interface SelectedContextFileWire {
  relative_path: string;
  score: number;
  reason: string;
  estimated_tokens: number;
  pinned: boolean;
}

export interface ContextSelectResponseWire {
  selected_files: SelectedContextFileWire[];
  total_tokens: number;
  accuracy: AccuracyLevel;
  warnings: string[];
}

export interface ContextItemWire {
  id: string;
  content: string;
  content_type?: ContentType;
  pinned?: boolean;
}

export interface ContextCompressRequestWire {
  items: ContextItemWire[];
  mode?: OptimizationMode;
  provider?: string;
  model?: string;
  project_id?: string;
}

export interface LogCompressRequestWire {
  command?: string;
  exit_code?: number;
  output: string;
  context_lines?: number;
  provider?: string;
  model?: string;
}

export interface HealthResponseWire {
  status: "ok" | "degraded";
  version: string;
  engine_ready: boolean;
  sqlite_ready: boolean;
}

export interface MetricsSummaryResponseWire {
  total_runs: number;
  total_original_tokens: number;
  total_optimized_tokens: number;
  total_tokens_saved: number;
  median_reduction_percentage?: number;
  fallback_count: number;
  by_accuracy?: Record<string, number>;
}

export interface RuntimeSettingsWire {
  default_mode: OptimizationMode;
  preserve_identifiers: boolean;
  allow_ai_semantic_compression: boolean;
  allow_remote_token_counting: boolean;
  cloud_sync_enabled: boolean;
  store_raw_history_locally: boolean;
  local_retention_days: number;
}

export type RuntimeSettingsUpdateWire = Partial<RuntimeSettingsWire>;

export interface ProviderModelInfoWire {
  model_name: string;
  supports_exact_local_count: boolean;
  pricing_version: string;
}

export interface ProviderCatalogEntryWire {
  id: string;
  display_name: string;
  models: ProviderModelInfoWire[];
}

export interface ProvidersResponseWire {
  providers: ProviderCatalogEntryWire[];
}

export interface ErrorDetailWire {
  code: string;
  message: string;
  request_id?: string;
}

export interface ErrorResponseWire {
  error: ErrorDetailWire;
}
