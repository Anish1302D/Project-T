-- Project T Reference Database Schema (Core 12 Entities + Local FTS5)
-- Target dialects: SQLite 3.45+ (local runtime) with standard ANSI/PostgreSQL notes.
-- Reference: docs/token-optimization-platform-architecture.md Section 11 & ADR-0008.
-- Note: By default, NO raw prompt text, optimized content, source code, or terminal
--       logs are persisted in analytics tables (metadata-only storage).

PRAGMA foreign_keys = ON;

-- 1. Cloud User Accounts (cloud control plane; optional local mirror row for linked account)
CREATE TABLE IF NOT EXISTS users (
    id TEXT PRIMARY KEY,
    email TEXT UNIQUE,
    display_name TEXT,
    created_at TEXT NOT NULL DEFAULT (CURRENT_TIMESTAMP),
    updated_at TEXT NOT NULL DEFAULT (CURRENT_TIMESTAMP)
);

-- 2. Registered Devices
CREATE TABLE IF NOT EXISTS devices (
    id TEXT PRIMARY KEY,
    user_id TEXT REFERENCES users(id) ON DELETE SET NULL,
    device_label TEXT NOT NULL,
    os_platform TEXT NOT NULL,
    created_at TEXT NOT NULL DEFAULT (CURRENT_TIMESTAMP),
    last_seen_at TEXT
);

-- 3. Registered Local Installations
CREATE TABLE IF NOT EXISTS installations (
    id TEXT PRIMARY KEY,
    device_id TEXT REFERENCES devices(id) ON DELETE SET NULL,
    runtime_version TEXT NOT NULL,
    schema_version TEXT NOT NULL DEFAULT '1.0',
    sync_enabled INTEGER NOT NULL DEFAULT 0 CHECK (sync_enabled IN (0, 1)),
    created_at TEXT NOT NULL DEFAULT (CURRENT_TIMESTAMP),
    last_active_at TEXT
);

-- 4. Provider Configuration Metadata
CREATE TABLE IF NOT EXISTS providers (
    id TEXT PRIMARY KEY, -- e.g. 'openai', 'anthropic', 'google', 'local'
    display_name TEXT NOT NULL,
    tokenizer_family TEXT NOT NULL,
    is_enabled INTEGER NOT NULL DEFAULT 1 CHECK (is_enabled IN (0, 1)),
    metadata_json TEXT NOT NULL DEFAULT '{}',
    updated_at TEXT NOT NULL DEFAULT (CURRENT_TIMESTAMP)
);

-- 5. Model and Versioned Tokenizer/Pricing Metadata
CREATE TABLE IF NOT EXISTS models (
    id TEXT PRIMARY KEY, -- e.g. 'openai:gpt-example'
    provider_id TEXT NOT NULL REFERENCES providers(id) ON DELETE CASCADE,
    model_name TEXT NOT NULL,
    tokenizer_name TEXT NOT NULL,
    context_window INTEGER,
    supports_exact_count INTEGER NOT NULL DEFAULT 0 CHECK (supports_exact_count IN (0, 1)),
    pricing_version TEXT NOT NULL,
    input_cost_per_1m_usd REAL,
    cached_input_cost_per_1m_usd REAL,
    output_cost_per_1m_usd REAL,
    updated_at TEXT NOT NULL DEFAULT (CURRENT_TIMESTAMP),
    UNIQUE (provider_id, model_name)
);

-- 6. Local Project Context Profiles (local-only by default)
CREATE TABLE IF NOT EXISTS project_profiles (
    id TEXT PRIMARY KEY,
    name TEXT NOT NULL,
    workspace_key_hash TEXT NOT NULL, -- local lookup key; not synced as anonymized identifier
    default_mode TEXT NOT NULL DEFAULT 'balanced' CHECK (default_mode IN ('safe', 'balanced', 'aggressive')),
    allowed_paths_json TEXT NOT NULL DEFAULT '[]',
    ignore_patterns_json TEXT NOT NULL DEFAULT '[]',
    retention_days INTEGER NOT NULL DEFAULT 30,
    created_at TEXT NOT NULL DEFAULT (CURRENT_TIMESTAMP),
    updated_at TEXT NOT NULL DEFAULT (CURRENT_TIMESTAMP)
);

-- 7. Context Fingerprints (strictly scoped by project_id + content_version)
CREATE TABLE IF NOT EXISTS context_fingerprints (
    id TEXT PRIMARY KEY,
    project_id TEXT NOT NULL REFERENCES project_profiles(id) ON DELETE CASCADE,
    content_version TEXT NOT NULL,
    file_hash TEXT NOT NULL,
    block_hash TEXT NOT NULL,
    simhash_64 TEXT,
    token_count INTEGER NOT NULL DEFAULT 0,
    accuracy TEXT NOT NULL DEFAULT 'estimated' CHECK (accuracy IN ('exact', 'estimated')),
    fresh_until TEXT,
    created_at TEXT NOT NULL DEFAULT (CURRENT_TIMESTAMP),
    UNIQUE (project_id, content_version, block_hash)
);

-- 8. User and Project Optimization Settings / Rules
CREATE TABLE IF NOT EXISTS optimization_rules (
    id TEXT PRIMARY KEY,
    installation_id TEXT REFERENCES installations(id) ON DELETE CASCADE,
    project_id TEXT REFERENCES project_profiles(id) ON DELETE CASCADE,
    scope TEXT NOT NULL CHECK (scope IN ('global', 'integration', 'project')),
    mode TEXT NOT NULL DEFAULT 'balanced' CHECK (mode IN ('safe', 'balanced', 'aggressive')),
    preserve_identifiers INTEGER NOT NULL DEFAULT 1 CHECK (preserve_identifiers IN (0, 1)),
    allow_ai_semantic_compression INTEGER NOT NULL DEFAULT 0 CHECK (allow_ai_semantic_compression IN (0, 1)),
    min_meaningful_savings_tokens INTEGER NOT NULL DEFAULT 10,
    rules_json TEXT NOT NULL DEFAULT '{}',
    version INTEGER NOT NULL DEFAULT 1,
    updated_at TEXT NOT NULL DEFAULT (CURRENT_TIMESTAMP)
);

-- 9. Optimization Runs (metadata-only by default)
CREATE TABLE IF NOT EXISTS optimization_runs (
    id TEXT PRIMARY KEY, -- e.g. 'run_001'
    request_id TEXT NOT NULL,
    installation_id TEXT REFERENCES installations(id) ON DELETE SET NULL,
    project_id TEXT REFERENCES project_profiles(id) ON DELETE SET NULL,
    provider_id TEXT REFERENCES providers(id) ON DELETE SET NULL,
    model_id TEXT REFERENCES models(id) ON DELETE SET NULL,
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
    methods_json TEXT NOT NULL DEFAULT '[]',
    warnings_json TEXT NOT NULL DEFAULT '[]',
    quality_score REAL, -- diagnostic metric Q in [0.0, 1.0]; not sole proof of quality
    duration_ms INTEGER NOT NULL DEFAULT 0,
    created_at TEXT NOT NULL DEFAULT (CURRENT_TIMESTAMP)
);

-- 10. Token Metrics (exact vs. estimated vs. provider-confirmed separation)
CREATE TABLE IF NOT EXISTS token_metrics (
    id TEXT PRIMARY KEY,
    run_id TEXT NOT NULL UNIQUE REFERENCES optimization_runs(id) ON DELETE CASCADE,
    original_tokens INTEGER NOT NULL CHECK (original_tokens >= 0),
    optimized_tokens INTEGER NOT NULL CHECK (optimized_tokens >= 0),
    tokens_saved INTEGER NOT NULL,
    reduction_percentage REAL NOT NULL,
    accuracy TEXT NOT NULL CHECK (accuracy IN ('exact', 'estimated')),
    provider_confirmed_original_tokens INTEGER,
    provider_confirmed_input_tokens INTEGER,
    created_at TEXT NOT NULL DEFAULT (CURRENT_TIMESTAMP)
);

-- 11. Cost Metrics (versioned pricing attribution)
CREATE TABLE IF NOT EXISTS cost_metrics (
    id TEXT PRIMARY KEY,
    run_id TEXT NOT NULL UNIQUE REFERENCES optimization_runs(id) ON DELETE CASCADE,
    pricing_version TEXT NOT NULL,
    estimated_cost_avoided_usd REAL NOT NULL DEFAULT 0.0,
    provider_confirmed_cost_avoided_usd REAL,
    currency TEXT NOT NULL DEFAULT 'USD',
    created_at TEXT NOT NULL DEFAULT (CURRENT_TIMESTAMP)
);

-- 12. Benchmark Results
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
    optimization_mode TEXT NOT NULL CHECK (optimization_mode IN ('safe', 'balanced', 'aggressive')),
    sample_count INTEGER NOT NULL CHECK (sample_count >= 0),
    unit_test_pass_rate REAL,
    constraint_preservation_rate REAL,
    identifier_preservation_rate REAL,
    median_reduction_pct REAL,
    p50_latency_ms REAL,
    p95_latency_ms REAL,
    negative_savings_count INTEGER NOT NULL DEFAULT 0,
    paired_quality_delta REAL,
    report_uri TEXT,
    executed_at TEXT NOT NULL DEFAULT (CURRENT_TIMESTAMP)
);

-- Indexes for fast local analytics & scoped fingerprint lookups
CREATE INDEX IF NOT EXISTS idx_runs_created_at ON optimization_runs(created_at);
CREATE INDEX IF NOT EXISTS idx_runs_integration ON optimization_runs(integration, created_at);
CREATE INDEX IF NOT EXISTS idx_fingerprints_scope ON context_fingerprints(project_id, file_hash, content_version);
CREATE INDEX IF NOT EXISTS idx_benchmarks_category ON benchmark_results(category, executed_at);

-- Optional Local SQLite FTS5 Virtual Table for BM25 Lexical Context Selection (metadata/chunks scoped locally)
-- In PostgreSQL cloud deployments, FTS5 is omitted; pgvector (optional P2) lives only in cloud if benchmark-justified.
CREATE VIRTUAL TABLE IF NOT EXISTS workspace_lexical_index USING fts5(
    project_id UNINDEXED,
    relative_path,
    symbols,
    content_excerpt,
    tokenize = 'porter unicode61'
);
