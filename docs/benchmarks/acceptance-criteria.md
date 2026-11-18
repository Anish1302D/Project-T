# Acceptance Targets and Release Gates

**Master Reference:** Sections 16 and 20 of [token-optimization-platform-architecture.md](../token-optimization-platform-architecture.md).  
**Related ADR:** [ADR-0012](../decisions/ADR-0012-benchmark-methodology-and-release-criteria.md).

---

## 1. Proposed Initial Acceptance Targets

> **Important:** These figures are **provisional engineering acceptance targets**, not measured benchmark results. Measured numbers will be published in `benchmarks/reports/` once implementation and paired runs are executed.

| Metric | Initial Acceptance Target | Verification Method |
|---|---|---|
| **Deterministic unit test pass rate** | `100%` | CI `pytest` + `vitest` suite |
| **Constraint preservation** | `100%` on curated protected-constraint tests | Constraint benchmark suite + `QualityValidator` assertions |
| **Identifier preservation** | `100%` on curated protected-identifier tests | Code/identifier benchmark suite + AST/symbol checks |
| **Median token reduction** | `>= 15%` on eligible benchmark inputs (reporting fallbacks honestly) | Benchmark runner across Prompt, Log, Context, Conversation datasets |
| **Task-quality regression** | No statistically meaningful degradation in paired evaluations | Paired LLM task-completion protocol + blinded human review |
| **Small-input local latency** | `< 100 ms` on agreed reference hardware | Latency benchmark (p50 / p95 logged with hardware spec) |
| **Local runtime availability** | `99%` during controlled integration testing | Local runtime soak/health integration suite |

---

## 2. CI & Milestone Quality Gates

### Milestone 1 (`v0.1.0` / `v0.2.0` Core Engine + Local Runtime)
- All unit, integration, and regression tests in `tests/` pass at `100%`.
- `100%` pass rate on curated protected-constraint and protected-identifier fixtures.
- Any validation failure or zero/negative-savings test case cleanly reverts to original content.
- Reproducible benchmark runner emits JSON/Markdown reports under `benchmarks/reports/` without crashing on edge cases (empty inputs, oversized inputs, malformed JSON, mixed-language code+prose).

### Integration & Release Gates (`v0.3.0` – `v1.0.0`)
- **Contract Sync Gate:** FastAPI runtime schema, JSON Schema (`contracts.schema.json`), and TypeScript types match with zero drift.
- **Security Gate:** Auth, CORS/origin checks, path traversal rejection, and secret-redaction tests pass in `tests/security/`.
- **E2E Gate:** Playwright tests verify Chrome extension site adapters / dashboard flows (`tests/e2e/`).
- **Gateway Gate:** Paired API benchmark verifies `provider_confirmed_input_tokens` reduction and zero tool/schema mutation.
