# Roadmap, MVP Scope, and Current Limitations

**Master Reference:** Sections 2, 14, 15, 20, and 23 of [token-optimization-platform-architecture.md](../token-optimization-platform-architecture.md).

---

## 1. MVP Scope Breakdown

### MVP v0.1 — Core Engine & Local Runtime
- **Must have:**
  - Content classification (`prompt`, `developer_prompt`, `source_code`, `json`, `documentation`, `terminal_output`, `conversation`, `tool_result`).
  - Exact deduplication and safe whitespace normalization.
  - Rule-based deterministic compression.
  - Constraint extraction and protected identifier handling.
  - `TokenizerAdapter` interface with `"exact"` / `"estimated"` labeling and fallback estimator.
  - `QualityValidator` with automatic fallback on validation failure or negligible/negative savings.
  - Policy modes: `safe`, `balanced`, `aggressive`.
  - FastAPI Local Runtime on `127.0.0.1:4765` with random per-install bearer auth.
  - SQLite metadata-only storage and structured optimization report.
  - Unit and regression tests + reproducible benchmark runner.
- **Should have:**
  - Near-duplicate candidate detection (`SimHash` / `MinHash`).
  - Terminal output error-window filtering.
  - Basic BM25 / SQLite FTS context selection.
  - Reversible transformation records.
- **Experimental:**
  - Optional AI-assisted semantic compression (off by default).

### MVP v0.2 — Developer Integration (VS Code)
- Optimize selected text with before/after diff preview and token savings estimate.
- Analyze selected prompt/context.
- Workspace file relevance analysis (`BM25`).
- Terminal output compression for user-selected terminal output.
- Local runtime connection/health diagnostics and local optimization history view.

### MVP v0.3 — Browser Integration (Chrome Manifest V3)
- Prompt optimization on explicitly supported ChatGPT, Claude, and Gemini web interfaces.
- User-triggered rewriting with original/optimized preview, token estimates, and Accept / Reject / Restore controls.

### MVP v0.4 — MCP Server & API Gateway
- MCP server exposing 7 narrow typed tools (`optimize_prompt`, `analyze_context`, `compress_terminal_output`, `select_relevant_files`, `deduplicate_context`, `estimate_tokens`, `get_optimization_report`).
- OpenAI, Anthropic, and Google provider adapters with request normalization, streaming pass-through, usage reconciliation, bypass mode, and fallback.

### MVP v0.5 — Cloud Control Plane & Dashboard
- Analytics dashboard (React + Vite + Tailwind).
- Cloud user authentication, PostgreSQL persistence, opt-in metadata/settings sync, cross-device configuration, and Docker packaging.

### Explicitly Out of Scope (First Release v1.0)
- Autonomous multi-agent orchestration.
- Custom foundation model training.
- Mandatory vector database (or `pgvector` before benchmarks justify it).
- Kubernetes orchestration.
- Enterprise organization / RBAC management.
- Billing / payment / complex subscription-tier infrastructure.
- Universal interception of arbitrary third-party AI extension or web traffic.

---

## 2. Phased Implementation Roadmap (10-Week Estimate)

> **Planning note:** This schedule is a planning estimate for focused engineering, not a delivery guarantee. Notice that Week 6 (MCP) and Week 7 (Browser) swap relative to MVP v0.3/v0.4 labeling in the master document; engineering follows the **engine-first** rule: validate Core Engine + Local Runtime before scaling client UIs.

| Week | Phase | Primary Work | Deliverable |
|---:|---|---|---|
| 1 | Foundation | Monorepo, tooling, shared contracts, CI, ADRs | Working repository foundation |
| 2 | Core engine | Classification, exact deduplication, rule-based compression, token adapter interface | Core engine alpha |
| 3 | Validation | Constraint extraction, protected identifiers, benchmarks, regression tests | Validated engine |
| 4 | Local runtime | FastAPI, SQLite, auth, settings, health and optimize endpoints | Local service |
| 5 | VS Code | Commands, sidebar, selected text, terminal output, preview | IDE alpha |
| 6 | Agent integration | MCP server, typed tools, VS Code MCP workflow, compatibility investigation | Agent integration alpha |
| 7 | Browser | Manifest V3, prompt field adapters, user review, supported site testing | Browser alpha |
| 8 | Gateway | Provider adapters, request normalization, streaming, usage reconciliation | Gateway alpha |
| 9 | Cloud | PostgreSQL, dashboard, auth, optional sync | Cloud beta |
| 10 | Release | E2E, security audit, benchmarks, documentation, packaging | Public MVP candidate |

---

## 3. First Engineering Milestone — Core Engine v0.1 Definition of Done

### Objective
A developer can submit text to the Local Runtime API (`http://127.0.0.1:4765/api/v1/optimize`), receive an optimized candidate, inspect exactly what transformations occurred, view token savings with accuracy labeling, and recover the unmodified original content.

### Definition of Done Checklist
- [x] Local runtime starts on `127.0.0.1:4765` and exposes `GET /api/v1/health`.
- [x] `POST /api/v1/optimize` accepts a schema-validated request and enforces bearer auth + CORS/origin rules.
- [x] Original content is always recoverable from the result/client flow.
- [x] Every transformation method applied is recorded in `optimization.methods[]`.
- [x] Token counts explicitly distinguish `"exact"` vs. `"estimated"`.
- [x] Constraint preservation and protected-identifier tests pass at 100% on curated fixtures.
- [x] Validation failure and non-positive/negligible savings paths cleanly return the original content.
- [x] Benchmark runner (`benchmarks/runner/`) produces reproducible JSON/Markdown reports.
- [x] Documentation clearly explains current limitations (below).

### Recommended 12-Step Sequence
1. Initialize repository and workspace tooling (`pnpm`, `Turborepo`, `pyproject.toml`, CI).
2. Finalize ADRs and canonical schemas (`packages/contracts`).
3. Create `packages/optimization-core` Python package.
4. Implement content classifier.
5. Implement protected-span & constraint extraction.
6. Implement exact deduplication.
7. Implement safe rule-based compression.
8. Implement `TokenizerAdapter` interface & generic/local estimator.
9. Implement `QualityValidator` & automatic rollback.
10. Build benchmark fixtures & reproducible runner.
11. Create FastAPI Local Runtime (`apps/local-runtime`) + SQLite metadata persistence.
12. Add integration tests and verify documentation matches implemented limits.

---

## 4. Current Limitations & Non-Goals

Per Section 2 and Section 20 ("Documentation explains current limitations"):

1. **Measured Release Capabilities & Evaluation Scope (`v1.0.0`):** All core packages (`contracts`, `optimization-core`, `provider-adapters`), local/cloud services (`local-runtime`, `api-gateway`, `services/`), and client apps (`vscode-extension`, `mcp-server`, `browser-extension`, `dashboard`) are implemented and verified in CI. Across the 8-category baseline benchmark ([baseline-report.md](../../benchmarks/reports/baseline-report.md), 26 cases on `Windows-11` / Python `3.14.7`), assertion, constraint, and identifier preservation rates are `100.0%` with eligible median token reductions of `45.95%` (prompt), `69.48%` (log), `25.55%` (conversation), `16.66%` (repository), and `15.09%` (api) at `p95 <= 5.69 ms`. The offline paired audit ([paired-evaluation-report.md](../../benchmarks/reports/paired-evaluation-report.md), 21 cases) confirms `15.78%` eligible median reduction with `0` objective degradations and `allow_ai_semantic_compression=False` by default. Live external commercial LLM trials and `docker compose up` integration depend on external provider API keys and an active Docker daemon respectively.
2. **Browser extension boundaries:** Operates only on user-triggered prompts inside explicitly supported web UIs (ChatGPT, Claude, Gemini). It cannot rewrite hidden server-side system prompts, background conversation history, or arbitrary `<all_urls>` text inputs.
3. **IDE & MCP traffic boundaries:** Neither the VS Code extension nor the MCP server can intercept or rewrite internal network requests made by unrelated third-party AI extensions.
4. **IDE compatibility claims:** Support for Antigravity, Cursor, Windsurf, or other agentic IDEs must be validated empirically against their current extension and MCP APIs before being advertised.
5. **Gateway routing requirement:** The API gateway optimizes traffic only when an application explicitly configures its provider base URL/routing to target the gateway.
6. **Token estimates vs. confirmed savings:** Local fallback estimates (`accuracy = "estimated"`) can differ from provider-billed input tokens. Furthermore, token reduction does not translate linearly to cost reduction when prompt caching, minimum billing increments, or semantic compression LLM overhead apply.
7. **Diagnostic score limits:** The internal quality formula `Q = 0.35I + 0.25C + 0.20S + 0.20R` is a structural diagnostic heuristic, **not** proof of downstream LLM semantic equivalence.
