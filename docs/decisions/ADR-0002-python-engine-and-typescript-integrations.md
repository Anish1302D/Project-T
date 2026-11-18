# ADR-0002: Python Optimization Engine and TypeScript Integration Layer

- **Status:** Accepted
- **Date:** 2026-11-18
- **Review Date:** 2027-02-18
- **Owners:** Project T Architecture
- **Related Master Doc Sections:** Sections 3, 4, 6, 9, 10, 13

---

## Context

Project T requires two very different execution profiles:

1. **Core optimization engine & runtime:** Text classification, AST/lexical analysis, constraint extraction, SimHash/MinHash near-duplicate detection, BM25 relevance scoring, rule-based and optional AI-assisted semantic compression, SQLite FTS indexing, FastAPI local/gateway HTTP endpoints, and reproducible evaluation/benchmarking.
2. **Developer & user-facing integrations:** Chrome Manifest V3 extension, VS Code Extension API client, React/Vite/Tailwind dashboard, and Model Context Protocol (MCP) server using the official TypeScript ecosystem or TypeScript extension hosts.

A critical architectural principle (Section 3.1) is **Engine Independence**: core optimization logic must not depend on browser, IDE, dashboard, gateway, or provider SDK code, and all integrations must reuse the exact same optimization logic rather than reimplementing compression heuristics in TypeScript.

## Decision

1. **Implement `packages/optimization-core` and `apps/local-runtime` (and `apps/api-gateway`) in Python 3.12+**, leveraging Pydantic for typed validation, FastAPI for HTTP transport, SQLite/FTS for local persistence and BM25 search, and Pytest for algorithm/benchmark testing.
2. **Implement user/host integrations (`browser-extension`, `vscode-extension`, `dashboard`, `mcp-server`, `shared-ui`, `shared-utils`) in TypeScript**, communicating with the optimization engine exclusively over versioned contracts via the authenticated Local Runtime HTTP API (`127.0.0.1:4765/api/v1`) or canonical contract packages.
3. **No duplicated optimization logic in TypeScript:** Extensions perform lightweight extraction, UI rendering, preview diffing, and user interaction (accept/reject/restore); all classification, deduplication, compression, token counting orchestration, and quality validation execute inside the Python engine.

## Alternatives Considered

### Option A: Pure TypeScript / Node.js everywhere (including optimization engine)
- **Pros:** Single language across extensions, MCP, dashboard, and engine; easy in-process embedding in VS Code extension host.
- **Cons:** Weaker ecosystem for NLP/text pipelines, benchmarking, FastAPI/Pydantic parity, and future optional ML/embedding evaluation; harder to share native code directly with Python-heavy AI evaluation tooling.
- **Why rejected:** Master Architecture selects Python 3.12+ / FastAPI / Pydantic as the primary core engine stack (Section 10) while keeping TypeScript for web/IDE/browser ecosystems.

### Option B: Dual implementation (TypeScript heuristics in browser/VS Code + Python engine on server)
- **Pros:** Browser and VS Code extensions could run offline without starting a local Python daemon.
- **Cons:** Inevitable divergence in compression rules, token counts, constraint protection, and quality validation across clients; doubles test and benchmark maintenance.
- **Why rejected:** Violates single-source-of-truth engine independence and creates inconsistent optimization results across integrations.

### Option C: Rust core with Python & WASM bindings
- **Pros:** High performance and in-browser WASM execution.
- **Cons:** Significantly slows v0.1–v0.5 iteration velocity for text heuristics, Pydantic contracts, and rapid benchmark experimentation.
- **Why rejected:** Premature optimization; Python deterministic pipelines already target `< 100 ms` small-input latency locally. Selective Rust/C-extension acceleration (e.g., `tiktoken` or C-backed hashing) can be adopted transparently inside Python if needed.

## Consequences

### Positive
- Single authoritative optimization pipeline tested once and consumed by VS Code, Chrome, MCP, and API Gateway.
- Strong typing at the boundary via Pydantic (Python) + JSON Schema + TypeScript interfaces.
- Clear isolation: browser/IDE failures or API quirks cannot corrupt engine logic.

### Negative / Trade-offs
- Browser and VS Code users must have the Local Runtime running (or packaged with the local installer/extension manager) to execute optimizations locally.
- Introduces an IPC/HTTP hop (`127.0.0.1:4765`) between TypeScript clients and the Python engine.

### Risks & Mitigations
- **Risk:** Local Runtime startup/lifecycle friction for end users in VS Code or Chrome.
  - **Mitigation:** Build explicit runtime health checks (`GET /api/v1/health`), clear connection diagnostics in VS Code/browser popups, and lifecycle management hooks in `apps/local-runtime/src/lifecycle/`.

## Review Triggers

- Review on **2027-02-18** or if HTTP IPC latency exceeds 15 ms p95 on small local payloads or local Python runtime packaging proves prohibitive for extension adoption.
