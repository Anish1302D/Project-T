import type { AccuracyLevel, IntegrationSource, OptimizationMode, OptimizationResult } from "@project-t/contracts";

export interface ModeOptionDescriptor {
  mode: OptimizationMode;
  label: string;
  description: string;
}

export const OPTIMIZATION_MODE_DESCRIPTORS: readonly ModeOptionDescriptor[] = [
  {
    mode: "safe",
    label: "Safe",
    description: "Low-risk deterministic normalization and strict preservation."
  },
  {
    mode: "balanced",
    label: "Balanced",
    description: "Deduplication, rule-based compression, and safe context filtering."
  },
  {
    mode: "aggressive",
    label: "Aggressive",
    description: "Broader compaction and pruning with hard constraint/identifier validation."
  }
] as const;

export interface OptimizationPreviewViewModel {
  requestId: string;
  originalTokens: number;
  optimizedTokens: number;
  tokensSaved: number;
  reductionLabel: string;
  accuracyLabel: string;
  accuracy: AccuracyLevel;
  fallbackTriggered: boolean;
  methods: string[];
  warnings: string[];
}

export function buildPreviewViewModel(result: OptimizationResult): OptimizationPreviewViewModel {
  return {
    requestId: result.requestId,
    originalTokens: result.originalTokens,
    optimizedTokens: result.optimizedTokens,
    tokensSaved: result.tokensSaved,
    reductionLabel: `${result.reductionPercentage.toFixed(2)}%`,
    accuracyLabel: result.accuracy === "exact" ? "Exact count" : "Estimated count",
    accuracy: result.accuracy,
    fallbackTriggered: !result.validationPassed || result.tokensSaved <= 0,
    methods: [...result.methods],
    warnings: [...result.warnings]
  };
}

export type AnalyticsGranularity = "daily" | "weekly" | "monthly";

export interface AnalyticsFilters {
  granularity: AnalyticsGranularity;
  start_date?: string;
  end_date?: string;
  provider?: string;
  integration?: IntegrationSource | "";
  mode?: OptimizationMode | "";
  accuracy?: AccuracyLevel | "";
  device_id?: string;
}

export interface ProviderModelBreakdown {
  provider: string;
  model: string;
  runs: number;
  original_tokens: number;
  optimized_tokens: number;
  tokens_saved: number;
  reduction_percentage: number;
  exact_runs: number;
  estimated_runs: number;
  estimated_cost_avoided_usd: number;
  confirmed_cost_avoided_usd: number;
}

export interface IntegrationBreakdown {
  integration: string;
  runs: number;
  original_tokens: number;
  optimized_tokens: number;
  tokens_saved: number;
  reduction_percentage: number;
  estimated_cost_avoided_usd: number;
}

export interface TrendBucket {
  bucket: string;
  runs: number;
  original_tokens: number;
  optimized_tokens: number;
  tokens_saved: number;
  exact_saved: number;
  estimated_saved: number;
  estimated_cost_avoided_usd: number;
}

export interface PairedDeviceSummary {
  device_id: string;
  device_label: string;
  os_platform: string;
  installation_id: string | null;
  runtime_version: string | null;
  sync_enabled: boolean;
  last_active_at: string | null;
}

export interface BenchmarkResultSummary {
  id: string;
  suite_name: string;
  category: string;
  dataset_version: string;
  engine_version: string;
  model_name: string;
  optimization_mode: string;
  sample_count: number;
  unit_test_pass_rate: number | null;
  constraint_preservation_rate: number | null;
  identifier_preservation_rate: number | null;
  median_reduction_pct: number | null;
  p50_latency_ms: number | null;
  p95_latency_ms: number | null;
  negative_savings_count: number;
  paired_quality_delta: number | null;
  executed_at: string;
}

export interface AnalyticsOverview {
  privacy_guarantee: string;
  totals: {
    total_runs: number;
    original_tokens: number;
    optimized_tokens: number;
    tokens_saved: number;
    reduction_percentage: number;
  };
  accuracy_breakdown: {
    exact_runs: number;
    exact_tokens_saved: number;
    estimated_runs: number;
    estimated_tokens_saved: number;
    provider_confirmed_runs: number;
    provider_confirmed_input_tokens: number;
    provider_confirmed_tokens_saved: number;
  };
  cost_avoided: {
    estimated_cost_avoided_usd: number;
    provider_confirmed_cost_avoided_usd: number;
    pricing_versions: string[];
  };
  by_provider_model: ProviderModelBreakdown[];
  by_integration: IntegrationBreakdown[];
  trends: TrendBucket[];
  granularity: AnalyticsGranularity;
  modes_and_methods: {
    by_mode: Array<{ mode: string; runs: number; tokens_saved: number }>;
    by_method: Array<{ method: string; count: number }>;
  };
  validation: {
    validated_runs: number;
    fallback_validation_failed: number;
    fallback_no_savings: number;
    fallback_error: number;
    fallback_total: number;
    fallback_rate_pct: number;
    validation_failure_rate_pct: number;
  };
  benchmarks: BenchmarkResultSummary[];
  latency: {
    sample_count: number;
    p50_ms: number;
    p90_ms: number;
    p95_ms: number;
    p99_ms: number;
    avg_ms: number;
  };
  devices: PairedDeviceSummary[];
}

export function formatTokenCount(count: number): string {
  return new Intl.NumberFormat("en-US").format(Math.round(count));
}

export function formatUsdCost(amount: number): string {
  if (amount > 0 && amount < 0.01) {
    return `$${amount.toFixed(4)}`;
  }
  return `$${amount.toFixed(2)}`;
}
