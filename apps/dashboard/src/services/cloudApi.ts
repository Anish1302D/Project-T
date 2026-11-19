import type { AnalyticsFilters, AnalyticsOverview } from "@project-t/shared-ui";

export interface AuthSessionResponse {
  access_token: string;
  token_type: string;
  user: {
    id: string;
    email: string;
    display_name: string;
  };
}

export async function loginCloudAccount(
  apiBaseUrl: string,
  email: string,
  password: string
): Promise<AuthSessionResponse> {
  const base = apiBaseUrl.trim().replace(/\/+$/, "");
  const res = await fetch(`${base}/api/cloud/v1/auth/login`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ email, password })
  });
  if (!res.ok) {
    throw new Error(`Authentication failed (HTTP ${res.status})`);
  }
  return (await res.json()) as AuthSessionResponse;
}

export async function registerCloudAccount(
  apiBaseUrl: string,
  email: string,
  displayName: string,
  password: string
): Promise<AuthSessionResponse> {
  const base = apiBaseUrl.trim().replace(/\/+$/, "");
  const res = await fetch(`${base}/api/cloud/v1/auth/register`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ email, display_name: displayName, password })
  });
  if (!res.ok) {
    throw new Error(`Registration failed (HTTP ${res.status})`);
  }
  return (await res.json()) as AuthSessionResponse;
}

export async function fetchAnalyticsOverview(
  apiBaseUrl: string,
  token: string,
  filters: AnalyticsFilters
): Promise<AnalyticsOverview> {
  const base = apiBaseUrl.trim().replace(/\/+$/, "");
  const params = new URLSearchParams();
  params.set("granularity", filters.granularity);
  if (filters.start_date) params.set("start_date", filters.start_date);
  if (filters.end_date) params.set("end_date", filters.end_date);
  if (filters.provider) params.set("provider", filters.provider);
  if (filters.integration) params.set("integration", filters.integration);
  if (filters.mode) params.set("mode", filters.mode);
  if (filters.accuracy) params.set("accuracy", filters.accuracy);
  if (filters.device_id) params.set("device_id", filters.device_id);

  const res = await fetch(`${base}/api/cloud/v1/analytics/overview?${params.toString()}`, {
    headers: {
      Authorization: `Bearer ${token}`
    }
  });
  if (!res.ok) {
    throw new Error(`Failed to fetch analytics overview (HTTP ${res.status})`);
  }
  return (await res.json()) as AnalyticsOverview;
}

export const OFFLINE_DEMO_OVERVIEW: AnalyticsOverview = {
  privacy_guarantee: "metadata_only_no_raw_prompts",
  totals: {
    total_runs: 24,
    original_tokens: 18420,
    optimized_tokens: 12960,
    tokens_saved: 5460,
    reduction_percentage: 29.64
  },
  accuracy_breakdown: {
    exact_runs: 14,
    exact_tokens_saved: 3680,
    estimated_runs: 10,
    estimated_tokens_saved: 1780,
    provider_confirmed_runs: 6,
    provider_confirmed_input_tokens: 4120,
    provider_confirmed_tokens_saved: 1510
  },
  cost_avoided: {
    estimated_cost_avoided_usd: 0.0159,
    provider_confirmed_cost_avoided_usd: 0.0038,
    pricing_versions: ["2026-11-v1"]
  },
  by_provider_model: [
    {
      provider: "openai",
      model: "gpt-4o",
      runs: 14,
      original_tokens: 11200,
      optimized_tokens: 7520,
      tokens_saved: 3680,
      reduction_percentage: 32.86,
      exact_runs: 14,
      estimated_runs: 0,
      estimated_cost_avoided_usd: 0.0092,
      confirmed_cost_avoided_usd: 0.0038
    },
    {
      provider: "anthropic",
      model: "claude-sonnet-4",
      runs: 6,
      original_tokens: 4520,
      optimized_tokens: 3310,
      tokens_saved: 1210,
      reduction_percentage: 26.77,
      exact_runs: 0,
      estimated_runs: 6,
      estimated_cost_avoided_usd: 0.0036,
      confirmed_cost_avoided_usd: 0
    },
    {
      provider: "google",
      model: "gemini-2.5-pro",
      runs: 4,
      original_tokens: 2700,
      optimized_tokens: 2130,
      tokens_saved: 570,
      reduction_percentage: 21.11,
      exact_runs: 0,
      estimated_runs: 4,
      estimated_cost_avoided_usd: 0.0031,
      confirmed_cost_avoided_usd: 0
    }
  ],
  by_integration: [
    {
      integration: "vscode",
      runs: 9,
      original_tokens: 7400,
      optimized_tokens: 5110,
      tokens_saved: 2290,
      reduction_percentage: 30.95,
      estimated_cost_avoided_usd: 0.0061
    },
    {
      integration: "gateway",
      runs: 6,
      original_tokens: 5300,
      optimized_tokens: 3790,
      tokens_saved: 1510,
      reduction_percentage: 28.49,
      estimated_cost_avoided_usd: 0.0042
    },
    {
      integration: "browser",
      runs: 5,
      original_tokens: 3420,
      optimized_tokens: 2450,
      tokens_saved: 970,
      reduction_percentage: 28.36,
      estimated_cost_avoided_usd: 0.0033
    },
    {
      integration: "mcp",
      runs: 4,
      original_tokens: 2300,
      optimized_tokens: 1610,
      tokens_saved: 690,
      reduction_percentage: 30.0,
      estimated_cost_avoided_usd: 0.0023
    }
  ],
  trends: [
    {
      bucket: "2026-11-17",
      runs: 7,
      original_tokens: 5200,
      optimized_tokens: 3720,
      tokens_saved: 1480,
      exact_saved: 980,
      estimated_saved: 500,
      estimated_cost_avoided_usd: 0.0044
    },
    {
      bucket: "2026-11-18",
      runs: 9,
      original_tokens: 6820,
      optimized_tokens: 4780,
      tokens_saved: 2040,
      exact_saved: 1410,
      estimated_saved: 630,
      estimated_cost_avoided_usd: 0.006
    },
    {
      bucket: "2026-11-19",
      runs: 8,
      original_tokens: 6400,
      optimized_tokens: 4460,
      tokens_saved: 1940,
      exact_saved: 1290,
      estimated_saved: 650,
      estimated_cost_avoided_usd: 0.0055
    }
  ],
  granularity: "daily",
  modes_and_methods: {
    by_mode: [
      { mode: "balanced", runs: 16, tokens_saved: 3920 },
      { mode: "safe", runs: 5, tokens_saved: 840 },
      { mode: "aggressive", runs: 3, tokens_saved: 700 }
    ],
    by_method: [
      { method: "whitespace_normalization", count: 19 },
      { method: "exact_paragraph_dedup", count: 14 },
      { method: "filler_phrase_trim", count: 12 },
      { method: "log_repeat_collapse", count: 6 }
    ]
  },
  validation: {
    validated_runs: 21,
    fallback_validation_failed: 1,
    fallback_no_savings: 2,
    fallback_error: 0,
    fallback_total: 3,
    fallback_rate_pct: 12.5,
    validation_failure_rate_pct: 4.17
  },
  benchmarks: [
    {
      id: "bench_prompt",
      suite_name: "core-engine-v1",
      category: "prompt",
      dataset_version: "2026-11-v1",
      engine_version: "0.1.0",
      model_name: "gpt-4o",
      optimization_mode: "balanced",
      sample_count: 5,
      unit_test_pass_rate: 1.0,
      constraint_preservation_rate: 1.0,
      identifier_preservation_rate: 1.0,
      median_reduction_pct: 45.95,
      p50_latency_ms: 1.292,
      p95_latency_ms: 3.46,
      negative_savings_count: 2,
      paired_quality_delta: null,
      executed_at: "2026-11-19T06:00:00Z"
    },
    {
      id: "bench_api",
      suite_name: "core-engine-v1",
      category: "api",
      dataset_version: "2026-11-v1",
      engine_version: "0.1.0",
      model_name: "gpt-4o",
      optimization_mode: "balanced",
      sample_count: 4,
      unit_test_pass_rate: 1.0,
      constraint_preservation_rate: 1.0,
      identifier_preservation_rate: 1.0,
      median_reduction_pct: 15.09,
      p50_latency_ms: 7.692,
      p95_latency_ms: 9.74,
      negative_savings_count: 1,
      paired_quality_delta: null,
      executed_at: "2026-11-19T06:00:00Z"
    }
  ],
  latency: {
    sample_count: 24,
    p50_ms: 4.2,
    p90_ms: 9.8,
    p95_ms: 11.4,
    p99_ms: 16.2,
    avg_ms: 5.15
  },
  devices: [
    {
      device_id: "dev_demo_workstation",
      device_label: "Workstation (Offline Preview)",
      os_platform: "Windows 11",
      installation_id: "inst_preview",
      runtime_version: "0.5.0",
      sync_enabled: false,
      last_active_at: "2026-11-19T06:00:00Z"
    }
  ]
};
