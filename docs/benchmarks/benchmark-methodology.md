# Benchmark Suite and Methodology (`benchmarks/`)

**Master Reference:** Sections 13, 16, and 20 of [token-optimization-platform-architecture.md](../token-optimization-platform-architecture.md).  
**Related ADR:** [ADR-0012](../decisions/ADR-0012-benchmark-methodology-and-release-criteria.md).

---

## 1. Proof Objectives

Every release candidate must demonstrate three empirical properties:

1. **Fewer tokens are sent to the provider.**
2. **The target model still completes the original task correctly.**
3. **Optimization latency and compute/API overhead do not outweigh the token savings.**

---

## 2. Eight Benchmark Categories

| Category | Dataset Scope (`benchmarks/datasets/`) | Primary Metrics Measured |
|---|---|---|
| **Prompt benchmark** | General & developer prompts across concise, verbose, and mixed formats | Token reduction %, intent retention, paired task accuracy |
| **Constraint benchmark** | Curated prompts with explicit negative prohibitions, positive requirements, and output formats | Exact constraint preservation rate (Target: `100%` on curated fixtures) |
| **Code benchmark** | Code refactoring, bug-fix, and generation tasks with symbols, imports, types, and literals | Identifier preservation rate (`100%` target), code-generation pass rate (unit tests) |
| **Repository benchmark** | Multi-file workspace task descriptions with ground-truth relevant files & tests | Recall@K, precision@K, token budget fit, associated test coverage |
| **Log benchmark** | Terminal, build, and test runner failures (compiler errors, stack traces, noisy installs) | Error extraction accuracy, diagnostic sufficiency, token reduction % |
| **Conversation benchmark** | Multi-turn agent/developer threads | Retention of goals, decisions, constraints, and unresolved tasks |
| **API benchmark** | End-to-end provider API requests routed through adapters/gateway | Actual provider-reported input tokens (`provider_confirmed_input_tokens`) vs pre-flight estimates |
| **Latency benchmark** | Small, medium, and large inputs across `safe`, `balanced`, and `aggressive` modes | p50, p95, p99 local processing time (ms) on documented reference hardware |

---

## 3. Runner & Reporting Architecture (`benchmarks/`)

```text
benchmarks/
├── datasets/     # Versioned JSONL / fixture suites per category (sanitized, reproducible)
├── evaluation/   # Paired evaluators, deterministic invariant checks, statistical comparison
├── reports/      # Generated JSON & Markdown benchmark reports (with reference hardware specs)
└── runner/       # CLI / Pytest runner producing reproducible artifacts
```

### Mandatory Reporting Rules
- Every benchmark run records: `engine_version`, `dataset_version`, `optimization_mode`, `provider`/`model`, `accuracy` (`exact` vs `estimated`), and reference hardware specs (for latency).
- Reports **must** surface:
  - **Failures** (any constraint/identifier break or paired task regression)
  - **Negative-savings / zero-savings / fallback counts** (never omit inputs where optimization did not help)
  - **Median and p10/p90 distribution**, not cherry-picked best-case examples.
- Any illustrative numbers shown in architecture docs (such as `32.92%` in Section 11 or `31.67%` in Section 12) are **illustrative examples only**, never cited as measured benchmark outcomes.
