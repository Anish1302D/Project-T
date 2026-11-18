# Project T — Phased Implementation Plan

**Document status:** Ready for execution (Phase 0 / Week 1 Foundation)  
**Source of truth:** [Master Technical Architecture](./token-optimization-platform-architecture.md) and specifications across `docs/`  
**Execution strategy:** Engine-first sequential delivery (Foundation & Core Engine -> Local Runtime -> Integrations one at a time -> Optional Cloud Control Plane & Release Hardening)

---

## 1. Current State & Execution Principles

### Starting Baseline
- **Existing artifacts:** Complete architecture specifications, OpenAPI 3.1 contract ([openapi-local-v1.yaml](./api/openapi-local-v1.yaml)), canonical JSON Schema ([contracts.schema.json](./api/contracts.schema.json)), reference SQLite/PostgreSQL DDL ([schema.sql](./architecture/schema.sql)), security/threat/privacy specs, benchmark methodology, and all 12 ADRs (`ADR-0001` through `ADR-0012`) reside in `docs/`.
- **Codebase state:** Pre-implementation; no `apps/`, `packages/`, `services/`, `benchmarks/`, `tests/`, or CI workflows exist yet, and `main` currently has no commits.

### Non-Negotiable Execution Rules
1. **Engine first ([Section 23](./token-optimization-platform-architecture.md#23-final-recommendation)):** Build, validate, and benchmark `packages/optimization-core` and `apps/local-runtime` before building downstream integration UIs simultaneously.
2. **Strict engine isolation ([ADR-0002](./decisions/ADR-0002-python-engine-and-typescript-integrations.md)):** `packages/optimization-core` must never import FastAPI, provider SDKs, browser APIs, or IDE extension APIs.
3. **Contract-first parity ([ADR-0004](./decisions/ADR-0004-canonical-api-schema-and-contract-generation.md)):** Python Pydantic models and TypeScript client contracts derive from or are CI-checked against `packages/contracts/schemas/`.
4. **Git discipline ([Section 18](./token-optimization-platform-architecture.md#18-git-workflow-and-engineering-standards)):** Never develop directly on `main`. Commit foundation docs, bootstrap `develop`, and land work via scoped `feature/*`, `fix/*`, `test/*`, and `docs/*` pull requests with passing tests and linters.
5. **Reconciled phase vs. tag mapping:** The master doc sequences **Week 6 (MCP)** before **Week 7 (Browser)** in Section 15 while grouping **v0.3 (Browser)** and **v0.4 (MCP & Gateway)** in Section 14 / Section 18. This plan follows the **10-week execution order** cleanly while tracking the exact release milestone tags below:

| Phase / Week | Target Tag / MVP Milestone | Primary Branch | Scope |
|---|---|---|---|
| Phase 0 (Pre-flight) | Baseline commit | `main` -> `develop` | Commit `docs/`, verify local toolchains, initialize branch protection |
| Phase 1 (Week 1) | Foundation | `feature/foundation` | Monorepo (`pnpm` + `Turborepo` + `pyproject.toml`), `packages/contracts`, CI skeleton |
| Phase 2 (Week 2) | Core Engine Alpha | `feature/optimization-core` | Classifier, exact dedup, whitespace/rule compression, terminal log extractor, `TokenizerAdapter` |
| Phase 3 (Week 3) | **v0.1.0 (MVP v0.1 Engine)** | `feature/optimization-core` + `test/benchmarks` | Constraint/protected-span locking, BM25/FTS context selection, `QualityValidator`, benchmark runner |
| Phase 4 (Week 4) | **v0.2.0 (MVP v0.1 Runtime)** | `feature/local-runtime` | FastAPI on `127.0.0.1:4765`, CSPRNG bearer auth, CORS/origin checks, SQLite DDL, all 10 `/api/v1` endpoints |
| Phase 5 (Week 5) | **v0.3.0 (MVP v0.2 VS Code)** | `feature/vscode-extension` | VS Code commands, diff preview, terminal output compression, workspace relevance, `SecretStorage` |
| Phase 6 (Week 6) | MCP Alpha (MVP v0.4 track) | `feature/mcp-server` | Typed MCP server (7 tools), workspace allowlist, compatibility check for VS Code/other IDEs |
| Phase 7 (Week 7) | **v0.4.0 (MVP v0.3 Browser)** | `feature/browser-extension` | Chrome Manifest V3, minimal host permissions, ChatGPT/Claude/Gemini `SiteAdapter`s, review UI |
| Phase 8 (Week 8) | **v0.5.0 (MVP v0.4 Gateway)** | `feature/api-gateway` | OpenAI/Anthropic/Google adapters, API Gateway, SSE streaming, usage reconciliation, API benchmarks |
| Phase 9 (Week 9) | Cloud Beta (MVP v0.5 Cloud) | `feature/cloud-dashboard` | `services/*` (auth, sync, analytics), PostgreSQL + optional Redis, React Dashboard (10 views), Docker |
| Phase 10 (Week 10) | **v1.0.0 (Universal Platform MVP)** | `test/release-validation`, `docs/release-sync` | Security audit, full 8-category + paired LLM benchmark suite, ADR ratification, packaging & release |

---

## 2. Phase 0 — Repository Bootstrap & Toolchain Check

### Tasks
1. Verify local development tools:
   - Python `3.12+` (`python --version`, `sqlite3` with FTS5 enabled)
   - Node.js LTS & `pnpm`
   - Git configured locally; Docker Desktop (needed by Phase 9)
2. Stage and create the initial baseline commit on `main` containing `docs/`.
3. Create and check out the `develop` integration branch (all subsequent phase branches branch from and merge back into `develop`).

### Exit Criteria
- `main` holds the baseline documentation suite cleanly.
- `develop` exists and is checked out for Phase 1.

---

## 3. Phase 1 (Week 1) — Monorepo Foundation & Canonical Contracts

**Branch:** `feature/foundation` -> PR to `develop`  
**References:** [ADR-0001](./decisions/ADR-0001-monorepo-and-workspace-tooling.md), [ADR-0004](./decisions/ADR-0004-canonical-api-schema-and-contract-generation.md), [repository-and-engineering-standards.md](./architecture/repository-and-engineering-standards.md), [canonical-contracts.md](./api/canonical-contracts.md).

### Files & Modules to Create
- Root configuration: `pnpm-workspace.yaml`, `turbo.json`, `pyproject.toml`, `.gitignore`, `.editorconfig`, `README.md`, `CONTRIBUTING.md`, `LICENSE`.
- `packages/contracts/`:
  - `schemas/contracts.v1.schema.json` (copied/linked from [contracts.schema.json](./api/contracts.schema.json))
  - `schemas/openapi-local-v1.yaml` (copied/linked from [openapi-local-v1.yaml](./api/openapi-local-v1.yaml))
  - `python/` (Pydantic v2 models matching wire DTOs)
  - `types/` (TypeScript `OptimizationMode`, `ContentType`, `OptimizationRequest`, `OptimizationResult`, `TokenizerAdapter`, `TokenCountResult`, and `snake_case` <-> `camelCase` mappers)
- `packages/shared-utils/` and `packages/shared-ui/` initial package scaffolds.
- `scripts/verify_contracts.py` (or TS/Python verification script) + `.github/workflows/ci.yml`.

### Implementation Steps
1. Initialize `pnpm` workspaces (`apps/*`, `packages/*`) and `turbo.json` pipelines (`build`, `test`, `lint`, `typecheck`).
2. Configure root `pyproject.toml` with Python `3.12+`, `pytest`, `ruff` / `mypy` (or `pyright`), and editable package layout for `packages/contracts`, `packages/optimization-core`, `packages/provider-adapters`, `apps/local-runtime`, and `apps/api-gateway`.
3. Implement Python Pydantic v2 contracts and TypeScript interfaces + mappers in `packages/contracts/`.
4. Finalize `ADR-0004` tooling selection (verify `datamodel-code-generator` / `openapi-typescript` or JSON Schema parity check) and wire contract drift detection into CI.

### Exit Criteria
- `pnpm install` and `turbo run build test lint` succeed on scaffold packages.
- `pytest` executes cleanly on `packages/contracts` round-trip serialization tests.
- Contract parity script verifies zero drift between `contracts.v1.schema.json`, Pydantic models, and TS types.

---

## 4. Phase 2 (Week 2) — Core Optimization Engine Alpha

**Branch:** `feature/optimization-core` -> PR to `develop`  
**References:** [optimization-engine.md](./architecture/optimization-engine.md), [pipeline-and-modes.md](./algorithms/pipeline-and-modes.md), [deduplication.md](./algorithms/deduplication.md), [compression-and-context-selection.md](./algorithms/compression-and-context-selection.md), [provider-and-tokenizer-adapters.md](./architecture/provider-and-tokenizer-adapters.md).

### Modules to Implement
- `packages/optimization-core/`:
  - `classifier/`: Rule-based + heuristic detector returning `ContentClassification` (`type`, `mapped_content_type` across the 8 `ContentType` values, `language`, `contains_code`, `contains_constraints`) plus mixed-segment detection for fenced code/JSON embedded inside prose.
  - `deduplication/`:
    - Stage 1: Safe line-ending (`\r\n` -> `\n`) and trailing-whitespace normalization (preserving indentation-sensitive code/YAML).
    - Stage 2–3: `SHA-256` block hashing and intra-request exact duplicate removal for eligible non-code/verified-identical blocks (skipping pinned spans).
    - Stage 4 (P1 prep): `SimHash` / `MinHash` signature module flagged for prose/log near-duplicate candidate detection only.
  - `compression/`:
    - P0 safe whitespace compaction.
    - P0 deterministic rule-based filler/boilerplate removal (operating strictly outside locked spans).
    - P0 terminal log compressor preserving command, exit code, first actionable error, relevant stack frames, file paths/line numbers, failure warnings, `context_lines` window, and test summary counts while stripping ANSI sequences.
  - `tokenization/` + `packages/provider-adapters/`:
    - `TokenizerAdapter` Python `Protocol` (`count_text`, optional `count_request`) returning `TokenCountResult(count, accuracy, model, provider)`.
    - `packages/provider-adapters/openai/` local `tiktoken` tokenizer adapter (marked `"exact"` when model encoding matches, `"estimated"` when chat framing approximated).
    - Generic offline fallback estimator strictly marked `accuracy = "estimated"`.
    - `packages/provider-adapters/registry/` initial versioned model/provider catalog (pricing separated from algorithms).

### Exit Criteria
- Unit tests in `tests/unit/` cover classifier mapping (`developer_instruction` -> `developer_prompt`), exact deduplication safety, whitespace preservation on Python/YAML/JSON, terminal log failure extraction, and `"exact"` vs `"estimated"` labeling (`100%` pass).
- Import boundary test confirms `packages/optimization-core` has zero imports from `apps/*`, `fastapi`, `pydantic`-web, or HTTP client SDKs.

---

## 5. Phase 3 (Week 3) — Constraint Protection, Validation, Context Selection & Benchmark Suite (`v0.1.0`)

**Branch:** `feature/optimization-core`, `test/benchmarks` -> PR to `develop`, tag **`v0.1.0`**  
**References:** [ADR-0006](./decisions/ADR-0006-pipeline-ordering-and-fallback-policy.md), [ADR-0007](./decisions/ADR-0007-protected-spans-and-constraint-preservation.md), [ADR-0012](./decisions/ADR-0012-benchmark-methodology-and-release-criteria.md), [classification-and-constraints.md](./algorithms/classification-and-constraints.md), [token-accounting-and-quality-scoring.md](./algorithms/token-accounting-and-quality-scoring.md), [acceptance-criteria.md](./benchmarks/acceptance-criteria.md).

### Modules to Implement
- `packages/optimization-core/`:
  - `constraints/`: Extract `objectives`, `targets`, `prohibitions` (`Do not...`, `Never...`, `Must...`, output format instructions) and detect/lock all **10 protected-span categories** (symbols/identifiers, imports/types, API endpoints/HTTP methods, error codes/messages, file paths/lines, JSON keys/schemas, explicit constraints, tool names/args, versions/configs, output formats) via immutable sentinel/interval locking.
  - `context-selection/`: BM25 + SQLite FTS5 lexical index ranker (`workspace_lexical_index` schema) scoring task relevance, filename/path matches, symbol/import references, 1-hop dependency links, associated test files, freshness (`file_hash`), and guaranteed `pinned_files` inclusion. Project- and version-scoped `context_fingerprints`.
  - `validation/`:
    - Hard `QualityValidator`: verify `constraints_preserved`, `identifiers_preserved`, and `structure_preserved` (JSON parseability + exact key set, balanced code fences, untouched tool schemas).
    - Compute diagnostic score $Q = 0.35I + 0.25C + 0.20S + 0.20R$ (tagged strictly as diagnostic only).
  - `pipeline/`: `PipelineOrchestrator` executing the 10-step fixed order across `safe`, `balanced`, and `aggressive` modes, enforcing `min_meaningful_savings`, recording `methods[]` & reversible trace metadata, and automatically reverting to `original_content` on validation failure, negative/zero savings, or error.
    - Leave optional AI-assisted semantic compression disabled by default behind an explicit disabled/experimental adapter hook (`allow_ai_semantic_compression = false`).
- `benchmarks/`:
  - `datasets/`: Curated initial fixture suites for `prompt`, `constraint`, `code`, `repository`, `log`, `conversation`, and `latency` categories.
  - `evaluation/` & `runner/`: Reproducible Python benchmark runner generating JSON & Markdown reports in `benchmarks/reports/` with reference hardware specs, negative-savings/fallback counts, and median/p10/p90 distributions.
- `tests/regression/`: Golden regression test cases from failed/edge fixtures (empty string, 1-token prompt, dense JSON, code with similar functions, negative savings).

### Exit Criteria (Engine Gate)
- `100%` deterministic unit & regression pass rate.
- `100%` pass rate on curated protected-constraint and protected-identifier benchmark fixtures.
- Benchmark runner produces reproducible baseline report in `benchmarks/reports/` demonstrating initial target validation (`>= 15%` median reduction on eligible fixtures and `< 100 ms` small-input latency on documented reference hardware, or documented adjustment in `ADR-0012` before proceeding).

---

## 6. Phase 4 (Week 4) — Local Runtime Service & SQLite Persistence (`v0.2.0` / Milestone 1 DoD)

**Branch:** `feature/local-runtime` -> PR to `develop`, tag **`v0.2.0`**  
**References:** [local-runtime-and-cloud-control-plane.md](./architecture/local-runtime-and-cloud-control-plane.md), [local-runtime-api.md](./api/local-runtime-api.md), [openapi-local-v1.yaml](./api/openapi-local-v1.yaml), [database-architecture.md](./architecture/database-architecture.md), [schema.sql](./architecture/schema.sql), [security-architecture.md](./security/security-architecture.md), [threat-model.md](./security/threat-model.md).

### Modules to Implement (`apps/local-runtime/src/`)
- `config/`: Typed runtime settings (`127.0.0.1:4765` default bind, refuse `0.0.0.0` by default, max body byte limit, request timeout, rate limit window, `store_raw_history_locally = false`, `cloud_sync_enabled = false`, workspace allowlist).
- `auth/`: CSPRNG per-installation bearer token initialization, OS credential store integration (`keyring` with `0600` ACL fallback), strict CORS origin allowlist, `Host`/`Origin` validator against DNS rebinding/CSRF, token rotation CLI command.
- `lifecycle/`: Startup/shutdown lifecycle, SQLite + FTS5 database bootstrap & migration runner (`infrastructure/database/sqlite/`) executing [schema.sql](./architecture/schema.sql), retention purge job.
- `server/`: FastAPI application implementing all 10 endpoints from `openapi-local-v1.yaml`:
  - `GET /api/v1/health` (unauthenticated minimal liveness/readiness)
  - `POST /api/v1/optimize`
  - `POST /api/v1/count`
  - `POST /api/v1/analyze`
  - `POST /api/v1/context/select` (with canonical path traversal check against approved workspace roots)
  - `POST /api/v1/context/compress`
  - `POST /api/v1/logs/compress`
  - `GET /api/v1/metrics` (metadata-only aggregation)
  - `GET /api/v1/settings` & `PUT /api/v1/settings`
  - `GET /api/v1/providers`
- Sanitized exception/logging middleware stripping `Authorization` headers, keys, and request `content` from logs and `422` validation responses.

### Exit Criteria (Milestone 1 Definition of Done)
- All 9 Milestone 1 DoD checklist items in [roadmap-mvp-and-limitations.md](./architecture/roadmap-mvp-and-limitations.md#3-first-engineering-milestone--core-engine-v01-definition-of-done) verified.
- FastAPI exported `/openapi.json` validated against `openapi-local-v1.yaml`.
- Security tests (`tests/security/`) verify `401` on missing/bad token, `403` on disallowed `Origin`/`Host` or workspace traversal, `413` on oversized payload, `429` on rate limit, and zero raw content/secrets in logs.
- Controlled integration soak test meets `99%` availability target.

---

## 7. Phase 5 (Week 5) — VS Code Extension (`v0.3.0` / MVP v0.2)

**Branch:** `feature/vscode-extension` -> PR to `develop`, tag **`v0.3.0`**  
**References:** [integration-architecture.md](./architecture/integration-architecture.md#3-vs-code-extension-appsvscode-extension).

### Modules to Implement (`apps/vscode-extension/src/`)
- `runtime/`: Typed Local Runtime HTTP client using `packages/contracts`, storing per-installation bearer token securely in VS Code `SecretStorage`, status bar indicator & `GET /health` check.
- `commands/`:
  - Optimize Selected Text (`POST /optimize`) with side-by-side VS Code diff editor preview + Accept / Reject / Restore Original actions.
  - Analyze Selected Prompt/Context (`POST /analyze`) showing detected type, constraints, protected spans, and baseline token estimate (`exact`/`estimated` badge).
  - Compress Selected Terminal Output (`POST /logs/compress`) retaining recoverable original.
- `context/` & `terminal/`: Explicit workspace-folder allowlist registration, workspace relevance command (`POST /context/select`), terminal selection helper.
- `views/` & `providers/`: Sidebar tree/webview showing connection status, optimization metrics (`/metrics`), and local optimization history (metadata-only by default).

### Exit Criteria
- `vitest` unit tests pass for runtime client, state/diff restoration, and command logic.
- Extension host integration tests pass against a running Local Runtime instance; README/UI makes zero claims of intercepting third-party AI extension traffic.

---

## 8. Phase 6 (Week 6) — MCP Server & IDE Compatibility Validation

**Branch:** `feature/mcp-server` -> PR to `develop`  
**References:** [ADR-0009](./decisions/ADR-0009-mcp-tool-naming-and-contracts.md), [mcp-tools-specification.md](./api/mcp-tools-specification.md).

### Modules to Implement (`apps/mcp-server/src/`)
- `server.ts`: Official TypeScript MCP SDK server connecting locally to `http://127.0.0.1:4765/api/v1` using installation bearer token.
- `tools/`: Implement all 7 narrow typed tools:
  1. `optimize_prompt`
  2. `analyze_context`
  3. `compress_terminal_output`
  4. `select_relevant_files`
  5. `deduplicate_context`
  6. `estimate_tokens`
  7. `get_optimization_report`
- Enforce Zod/JSON Schema argument validation, per-tool input caps (`512 KB` / `1 MB` / `100` items), canonical workspace root confinement on `select_relevant_files`, zero subprocess/shell execution, recoverable original references, and explicit `local-only` vs. optional cloud descriptions.
- `resources/`: Optional read-only optimization report/settings status resources.
- **IDE compatibility spike:** Validate MCP registration/invocation in VS Code first; separately test current extension/MCP interfaces for Antigravity, Cursor, and Windsurf before documenting any compatibility claims, and ratify `ADR-0009`.

### Exit Criteria
- MCP contract & security tests pass (invalid args, oversized payloads, path traversal escape attempts rejected).
- End-to-end tool invocation verified from VS Code MCP client to Local Runtime.

---

## 9. Phase 7 (Week 7) — Browser Extension (`v0.4.0` / MVP v0.3)

**Branch:** `feature/browser-extension` -> PR to `develop`, tag **`v0.4.0`**  
**References:** [ADR-0010](./decisions/ADR-0010-browser-permissions-and-site-adapters.md), [integration-architecture.md](./architecture/integration-architecture.md#2-browser-extension-appsbrowser-extension), [security-architecture.md](./security/security-architecture.md#31-browser-extension-appsbrowser-extension).

### Modules to Implement (`apps/browser-extension/src/`)
- `manifest.json`: Chrome Manifest V3 requesting minimal permissions strictly for supported ChatGPT, Claude, and Gemini origins + `http://127.0.0.1:4765/*` (no `<all_urls>`, no `cookies`).
- `integrations/`: Common `SiteAdapter` interface and dedicated adapters for ChatGPT, Claude, and Gemini prompt editors (`textarea`/`contenteditable`/ProseMirror text extraction & controlled replacement with clipboard fallback).
- `content/` & `popup/`: Explicit user-triggered optimize action, inline/popup diff preview, token count + reduction % + `"exact"`/`"estimated"` badge, **Accept**, **Reject**, and **Restore Original** controls.
- `background/` & `options/`: Service worker handling authenticated Local Runtime `fetch` calls; options page for pairing local installation token & mode preference (zero provider API keys stored).

### Exit Criteria
- Vitest adapter tests pass against DOM fixtures for ChatGPT, Claude, and Gemini editors.
- Playwright E2E tests (`tests/e2e/`) validate optimize -> preview -> accept -> restore flow against fixture pages; manifest audit verifies minimal permissions and zero secrets in bundle; ratify `ADR-0010`.

---

## 10. Phase 8 (Week 8) — Provider Adapters & API Gateway (`v0.5.0` / MVP v0.4)

**Branch:** `feature/api-gateway` -> PR to `develop`, tag **`v0.5.0`**  
**References:** [provider-and-tokenizer-adapters.md](./architecture/provider-and-tokenizer-adapters.md), [api-gateway-specification.md](./api/api-gateway-specification.md), [paired-evaluation-and-accounting.md](./benchmarks/paired-evaluation-and-accounting.md).

### Modules to Implement
- Expand `packages/provider-adapters/`:
  - `anthropic/`: Provider message-counting API adapter (opt-in online `"exact"` + offline `"estimated"` fallback) + Anthropic Messages serializer.
  - `google/`: Gemini token-counting adapter + GenerateContent serializer.
  - `registry/`: Complete versioned pricing catalog (`pricing_version`) across supported OpenAI, Anthropic, and Google models.
- Implement `apps/api-gateway/src/`:
  - `routes/` & `providers/`: Normalized proxy routes for OpenAI, Anthropic, and Google APIs.
  - `middleware/`: Auth/key pass-through or OS/managed credential injection, `X-ProjectT-Bypass` support, `Idempotency-Key` preservation, secret & request-body log redaction, fail-open fallback to unmodified original request on optimizer error/timeout.
  - Structural invariance verifier guaranteeing `tools[]`, function arguments, `response_format`, and JSON schemas are never silently altered.
  - `streaming/`: Transparent SSE chunked pass-through with asynchronous post-stream `usage` extraction.
  - `usage/`: Persist `provider_confirmed_input_tokens` and `cost_metrics` reconciling pre-flight estimates vs. provider-reported usage.

### Exit Criteria
- Gateway integration tests verify streaming SSE parity, zero tool/JSON schema mutation, bypass header, fail-open fallback, and redacted logs.
- Execute **API Benchmark** (Category 7) comparing pre-flight counts against `provider_confirmed_input_tokens` across real/sandboxed provider requests.

---

## 11. Phase 9 (Week 9) — Cloud Control Plane, Dashboard & Docker Packaging (MVP v0.5)

**Branch:** `feature/cloud-dashboard` -> PR to `develop`  
**References:** [ADR-0008](./decisions/ADR-0008-sqlite-local-and-postgresql-cloud-sync-boundaries.md), [ADR-0011](./decisions/ADR-0011-privacy-telemetry-retention-and-storage.md), [database-architecture.md](./architecture/database-architecture.md), [integration-architecture.md](./architecture/integration-architecture.md#6-cloud-dashboard-appsdashboard).

### Modules to Implement
- `infrastructure/database/postgres/` & `infrastructure/docker/`: PostgreSQL migrations mirroring the cloud-eligible subset of [schema.sql](./architecture/schema.sql), `Dockerfile`s, and `docker-compose.yml` (PostgreSQL + optional Redis + control-plane API + Dashboard; no Kubernetes or mandatory vector DB).
- `services/`:
  - `authentication/`: Cloud account auth and local installation/device pairing.
  - `cloud-sync/`: Opt-in synchronization for `optimization_rules` and **metadata-only** `optimization_runs`/`token_metrics`/`cost_metrics` (enforcing idempotent `(installation_id, run_id)` upsert and strictly rejecting raw prompts/source code or unsalted low-entropy content hashes).
  - `analytics/`: Aggregated multi-device rollup queries separating `estimated`, `exact`, `provider-confirmed`, and `cost avoided`.
- `apps/dashboard/` (React + Vite + Tailwind + `packages/shared-ui`):
  - Implement all 10 required views (original vs. optimized tokens, net tokens saved, estimated cost avoided, provider/model breakdown, integration breakdown, daily/weekly/monthly trend, modes/methods breakdown, validation failure & fallback rates, benchmark summaries, latency percentiles).

### Exit Criteria
- Cloud sync boundary tests confirm raw prompt/code/file paths are never transmitted during default metadata sync and local runtime works 100% identically when cloud services are offline.
- Playwright E2E tests verify dashboard rendering and filtering; `docker compose up` smoke tests pass cleanly; ratify `ADR-0008`.

---

## 12. Phase 10 (Week 10) — Security Audit, Paired Benchmarks & Release (`v1.0.0`)

**Branches:** `test/release-validation`, `docs/release-sync` -> merge `develop` -> `main`, tag **`v1.0.0`**  
**References:** [acceptance-criteria.md](./benchmarks/acceptance-criteria.md), [benchmark-methodology.md](./benchmarks/benchmark-methodology.md), [paired-evaluation-and-accounting.md](./benchmarks/paired-evaluation-and-accounting.md), [threat-model.md](./security/threat-model.md).

### Tasks
1. **Security audit (`tests/security/`):** Full verification across all 9 threats in [threat-model.md](./security/threat-model.md) (localhost auth/CORS/DNS rebinding, path traversal, Manifest V3 minimal permissions, zero frontend secrets, log redaction, cache project scoping).
2. **Full 8-category benchmark & paired LLM evaluation:**
   - Run all 8 categories (`prompt`, `constraint`, `code`, `repository`, `log`, `conversation`, `api`, `latency`).
   - Execute paired evaluation protocol against fixed model versions with objective assertions + human review on subjective prompts; publish transparent report in `benchmarks/reports/` including failures and negative-savings counts.
   - Verify whether P1/P2 candidates (`SimHash`/`MinHash`, optional AI semantic compression, or embeddings) earned empirical benchmark justification; keep unvalidated experimental features disabled by default.
3. **Documentation & ADR ratification:**
   - Update `Proposed` ADRs (`ADR-0004`, `0008`, `0009`, `0010`, `0012`) to `Accepted` with empirical review notes.
   - Update [roadmap-mvp-and-limitations.md](./architecture/roadmap-mvp-and-limitations.md) so documented limitations, supported integrations, and measured benchmark summaries reflect actual tested capabilities.
4. **Release packaging:** Build reproducible Docker images, VS Code `.vsix`, Chrome MV3 bundle, and Python wheels; merge `develop` -> `main` via release PR and tag `v1.0.0`.

### Release Gate Checklist
- [ ] Deterministic unit & regression tests: `100%` pass
- [ ] Curated protected-constraint & protected-identifier fixtures: `100%` pass
- [ ] Median token reduction on eligible benchmarks: `>= 15%` (with negative/fallback cases reported)
- [ ] Paired LLM evaluation: no statistically meaningful task-quality degradation
- [ ] Small-input local latency: `< 100 ms` on agreed reference hardware
- [ ] Local runtime stability: `99%` availability in controlled soak tests
- [ ] All security, E2E, and contract-parity CI checks green

---

## 13. Key Implementation Risks & Built-In Safeguards

| Risk | Affected Phase | Mitigation Built Into Plan |
|---|---|---|
| **Contract drift between Python & TS** | Phase 1+ | Canonical JSON Schema + OpenAPI CI diff script before Phase 2 starts |
| **Circular quality self-validation via `Q`** | Phase 3, 10 | Hard binary `QualityValidator` checks + mandatory paired LLM evaluation protocol |
| **Local runtime startup friction for extension users** | Phase 4–7 | Clear `/health` diagnostics, `SecretStorage`/options pairing UI, lifecycle manager |
| **AI website DOM markup breaking adapters** | Phase 7 | Isolated `SiteAdapter` modules + fixture Playwright E2E tests + clipboard fallback |
| **Premature complexity (embeddings / microservices / K8s)** | All phases | Explicitly deferred (`pgvector` P2 only if benchmark-justified; modular monorepo only) |
| **Misleading savings or cost claims** | Phase 2–10 | Mandatory `exact` vs `estimated` vs `provider-confirmed` badges + versioned pricing |
