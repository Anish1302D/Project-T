-- Project T Cloud Control Plane PostgreSQL Schema (MVP v0.5)
-- Mirrors strictly the cloud-eligible subset of docs/architecture/schema.sql per ADR-0008 & ADR-0011.
-- Intentionally EXCLUDES local-only tables:
--   - project_profiles (local workspace roots/ignore patterns)
--   - context_fingerprints (low-entropy block/file hashes scoped locally)
--   - workspace_lexical_index (SQLite FTS5)
-- Optional pgvector remains deferred to P2 unless justified by benchmarks.
-- Stores metadata-only optimization/token/cost metrics (never raw prompts, code, or logs).

-- 1. Cloud User Accounts
CREATE TABLE IF NOT EXISTS users (
    id TEXT PRIMARY KEY,
    email TEXT NOT NULL UNIQUE,
    display_name TEXT NOT NULL,
    password_hash TEXT NOT NULL,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

-- 2. Registered Devices
CREATE TABLE IF NOT EXISTS devices (
    id TEXT PRIMARY KEY,
    user_id TEXT NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    device_label TEXT NOT NULL,
    os_platform TEXT NOT NULL,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    last_seen_at TIMESTAMPTZ
);

-- 3. Registered Local Installations (linked optionally when user pairs a device)
CREATE TABLE IF NOT EXISTS installations (
    id TEXT PRIMARY KEY,
    device_id TEXT REFERENCES devices(id) ON DELETE SET NULL,
    user_id TEXT REFERENCES users(id) ON DELETE SET NULL,
    runtime_version TEXT NOT NULL,
    schema_version TEXT NOT NULL DEFAULT '1.0',
    sync_enabled BOOLEAN NOT NULL DEFAULT FALSE,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    last_active_at TIMESTAMPTZ
);

-- 4. Provider Configuration Metadata
CREATE TABLE IF NOT EXISTS providers (
    id TEXT PRIMARY KEY,
    display_name TEXT NOT NULL,
    tokenizer_family TEXT NOT NULL,
    is_enabled BOOLEAN NOT NULL DEFAULT TRUE,
    metadata_json JSONB NOT NULL DEFAULT '{}'::jsonb,
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

-- 5. Model and Versioned Tokenizer/Pricing Metadata
CREATE TABLE IF NOT EXISTS models (
    id TEXT PRIMARY KEY,
    provider_id TEXT NOT NULL REFERENCES providers(id) ON DELETE CASCADE,
    model_name TEXT NOT NULL,
    tokenizer_name TEXT NOT NULL,
    context_window INTEGER,
    supports_exact_count BOOLEAN NOT NULL DEFAULT FALSE,
    pricing_version TEXT NOT NULL,
    input_cost_per_1m_usd DOUBLE PRECISION,
    cached_input_cost_per_1m_usd DOUBLE PRECISION,
    output_cost_per_1m_usd DOUBLE PRECISION,
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    UNIQUE (provider_id, model_name)
);

-- 6. Synced Optimization Settings / Rules (project_id optional symbolic ref only; never filesystem path)
CREATE TABLE IF NOT EXISTS optimization_rules (
    id TEXT PRIMARY KEY,
    installation_id TEXT NOT NULL REFERENCES installations(id) ON DELETE CASCADE,
    project_id TEXT,
    scope TEXT NOT NULL CHECK (scope IN ('global', 'integration', 'project')),
    mode TEXT NOT NULL DEFAULT 'balanced' CHECK (mode IN ('safe', 'balanced', 'aggressive')),
    preserve_identifiers BOOLEAN NOT NULL DEFAULT TRUE,
    allow_ai_semantic_compression BOOLEAN NOT NULL DEFAULT FALSE,
    min_meaningful_savings_tokens INTEGER NOT NULL DEFAULT 10,
    rules_json JSONB NOT NULL DEFAULT '{}'::jsonb,
    version INTEGER NOT NULL DEFAULT 1,
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

-- 7. Synced Optimization Runs (metadata-only; idempotent by (installation_id, run_id))
CREATE TABLE IF NOT EXISTS optimization_runs (
    id TEXT PRIMARY KEY, -- composite key '<installation_id>:<run_id>'
    run_id TEXT NOT NULL,
    request_id TEXT NOT NULL,
    installation_id TEXT NOT NULL REFERENCES installations(id) ON DELETE CASCADE,
    device_id TEXT REFERENCES devices(id) ON DELETE SET NULL,
    provider_id TEXT REFERENCES providers(id) ON DELETE SET NULL,
    model_id TEXT REFERENCES models(id) ON DELETE SET NULL,
    model_name TEXT NOT NULL,
    integration TEXT NOT NULL CHECK (integration IN ('vscode', 'browser', 'mcp', 'gateway', 'cli', 'api')),
    content_type TEXT NOT NULL CHECK (
        content_type IN (
            'prompt',
            'developer_prompt',
            'source_code',
            'json',
            'documentation',
            'terminal_output',
            'conversation',
            'tool_result'
        )
    ),
    optimization_mode TEXT NOT NULL CHECK (optimization_mode IN ('safe', 'balanced', 'aggressive')),
    status TEXT NOT NULL CHECK (status IN ('validated', 'fallback_validation_failed', 'fallback_no_savings', 'fallback_error')),
    methods_json JSONB NOT NULL DEFAULT '[]'::jsonb,
    warnings_json JSONB NOT NULL DEFAULT '[]'::jsonb,
    quality_score DOUBLE PRECISION,
    duration_ms INTEGER NOT NULL DEFAULT 0,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    UNIQUE (installation_id, run_id)
);

-- 8. Token Metrics (exact vs. estimated vs. provider-confirmed separation)
CREATE TABLE IF NOT EXISTS token_metrics (
    id TEXT PRIMARY KEY,
    run_id TEXT NOT NULL UNIQUE REFERENCES optimization_runs(id) ON DELETE CASCADE,
    original_tokens INTEGER NOT NULL CHECK (original_tokens >= 0),
    optimized_tokens INTEGER NOT NULL CHECK (optimized_tokens >= 0),
    tokens_saved INTEGER NOT NULL,
    reduction_percentage DOUBLE PRECISION NOT NULL,
    accuracy TEXT NOT NULL CHECK (accuracy IN ('exact', 'estimated')),
    provider_confirmed_original_tokens INTEGER,
    provider_confirmed_input_tokens INTEGER,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

-- 9. Cost Metrics (versioned pricing attribution)
CREATE TABLE IF NOT EXISTS cost_metrics (
    id TEXT PRIMARY KEY,
    run_id TEXT NOT NULL UNIQUE REFERENCES optimization_runs(id) ON DELETE CASCADE,
    pricing_version TEXT NOT NULL,
    estimated_cost_avoided_usd DOUBLE PRECISION NOT NULL DEFAULT 0.0,
    provider_confirmed_cost_avoided_usd DOUBLE PRECISION,
    currency TEXT NOT NULL DEFAULT 'USD',
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

-- 10. Quality Benchmark Results
CREATE TABLE IF NOT EXISTS benchmark_results (
    id TEXT PRIMARY KEY,
    suite_name TEXT NOT NULL,
    category TEXT NOT NULL CHECK (
        category IN (
            'prompt',
            'constraint',
            'code',
            'repository',
            'log',
            'conversation',
            'api',
            'latency'
        )
    ),
    dataset_version TEXT NOT NULL,
    engine_version TEXT NOT NULL,
    model_id TEXT REFERENCES models(id) ON DELETE SET NULL,
    model_name TEXT NOT NULL DEFAULT 'gpt-4o',
    optimization_mode TEXT NOT NULL CHECK (optimization_mode IN ('safe', 'balanced', 'aggressive')),
    sample_count INTEGER NOT NULL CHECK (sample_count >= 0),
    unit_test_pass_rate DOUBLE PRECISION,
    constraint_preservation_rate DOUBLE PRECISION,
    identifier_preservation_rate DOUBLE PRECISION,
    median_reduction_pct DOUBLE PRECISION,
    p50_latency_ms DOUBLE PRECISION,
    p95_latency_ms DOUBLE PRECISION,
    negative_savings_count INTEGER NOT NULL DEFAULT 0,
    paired_quality_delta DOUBLE PRECISION,
    report_uri TEXT,
    executed_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

-- Analytics query indexes
CREATE INDEX IF NOT EXISTS idx_cloud_runs_created_at ON optimization_runs(created_at DESC);
CREATE INDEX IF NOT EXISTS idx_cloud_runs_installation ON optimization_runs(installation_id, created_at DESC);
CREATE INDEX IF NOT EXISTS idx_cloud_runs_integration ON optimization_runs(integration, created_at DESC);
CREATE INDEX IF NOT EXISTS idx_cloud_runs_provider ON optimization_runs(provider_id, model_name);
CREATE INDEX IF NOT EXISTS idx_cloud_benchmarks_category ON benchmark_results(category, executed_at DESC);
