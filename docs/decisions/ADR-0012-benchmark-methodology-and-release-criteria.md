# ADR-0012: Benchmark Methodology and Release Acceptance Criteria

- **Status:** Accepted
- **Date:** 2026-11-18
- **Ratified:** 2026-11-19 (Phase 10 — 8-category benchmark runner and paired invariant audit verified)
- **Review Date:** 2027-02-18
- **Owners:** Project T Architecture
- **Related Master Doc Sections:** Sections 7.8, 7.9, 16, 19, 20, 23

---

## Context

Claiming "X% token savings" without proving that downstream models still solve the user's actual task—or equating heuristic token estimates directly with confirmed dollar savings—is misleading. The platform must empirically prove three core properties (Section 16):

1. Fewer tokens are sent to the provider.
2. The model still completes the original task correctly.
3. Optimization overhead (latency and optional AI-compression cost) does not outweigh the savings.

Furthermore, the internal diagnostic quality formula `Q = 0.35I + 0.25C + 0.20S + 0.20R` evaluates structural/rule preservation inside the optimizer, so relying on `Q` alone creates circular self-validation.

## Decision

1. **Eight-Category Benchmark Suite (`benchmarks/`):**
   Organize evaluation fixtures and runners across 8 distinct categories:
   - Prompt benchmark (intent & instruction preservation)
   - Constraint benchmark (required & forbidden action retention)
   - Code benchmark (code-generation correctness & identifier preservation)
   - Repository benchmark (file selection relevance & coverage)
   - Log benchmark (error extraction & diagnostic usefulness)
   - Conversation benchmark (retention of goals, decisions, unresolved tasks)
   - API benchmark (actual provider-reported input tokens)
   - Latency benchmark (optimization processing overhead)
2. **Paired Evaluation Protocol:**
   - Execute original vs. optimized prompts against the **exact same fixed model/version**, tools, settings, and sampling parameters.
   - Evaluate using objective task-completion assertions (unit tests, pass/fail checks, schema validation) plus human review for subjective tasks.
   - Explicitly record and report **failures and negative-savings cases** (no cherry-picking).
   - Never treat the internal diagnostic score `Q` as sufficient proof of task-level semantic equivalence.
3. **Strict Accounting Definitions:**
   - **Estimated savings:** Local heuristic/tokenizer estimate (`accuracy = "estimated"`).
   - **Exact pre-flight count:** Authoritative local/provider tokenizer count (`accuracy = "exact"`).
   - **Provider-confirmed savings:** Verified directly from provider usage response tokens.
   - **Cost avoided:** Calculated strictly using versioned model pricing rules applied to confirmed billable usage (never equated 1:1 with raw token reduction without pricing/caching context).
4. **Provisional Release Acceptance Targets (Subject to Baseline Validation):**
   - Deterministic unit test pass rate: `100%`
   - Constraint preservation on curated protected-constraint tests: `100%`
   - Identifier preservation on curated protected-identifier tests: `100%`
   - Median token reduction on eligible benchmark inputs: `>= 15%`
   - Task-quality regression in paired evaluation: No statistically meaningful degradation
   - Small-input local latency on agreed reference hardware: `< 100 ms`
   - Local runtime availability during controlled testing: `99%`
5. **Engine-First Gate:**
   - Core engine acceptance benchmarks must pass on Milestone 1 (`v0.1`) before scaling up multiple client UIs.

## Alternatives Considered

### Option A: Validate quality using only internal heuristic score `Q` and compression ratio
- **Pros:** Free, instant, requires no LLM evaluation calls.
- **Cons:** Circular validation; misses subtle instruction degradation that passes regex/AST checks.
- **Why rejected:** Explicitly prohibited by Section 16 ("Do not use the optimizer's own quality score as the only evidence of quality").

### Option B: Ad-hoc manual prompt checks without paired datasets
- **Pros:** Fast initially.
- **Cons:** Cannot detect regressions across commits or compare Safe/Balanced/Aggressive tradeoffs objectively.
- **Why rejected:** Violates Milestone 1 Definition of Done ("Benchmark runner produces reproducible reports").

## Consequences

### Positive
- Prevents shipping compression rules that inflate apparent savings while degrading coding/reasoning accuracy.
- Produces reproducible JSON/Markdown benchmark reports in CI and prior to releases.
- Establishes honest public claims distinguishing targets vs measured results and estimated vs provider-confirmed savings.

### Negative / Trade-offs
- Paired LLM evaluations incur API costs and non-deterministic variance requiring repeated trials/fixed seeds or low-temperature runs.

### Risks & Mitigations
- **Risk:** Small-input latency hardware dependency (`< 100 ms`) varies wildly across developer laptops vs CI runners.
  - **Mitigation:** Document reference hardware specifications alongside latency reports in `benchmarks/reports/` and measure relative regression percentages in CI.

## Review Triggers

- Reviewed and accepted in Phase 10 (**2026-11-19**):
  - `benchmarks/runner/run_benchmarks.py` covers all 8 categories (`prompt`, `constraint`, `code`, `repository`, `log`, `conversation`, `api`, `latency`) across 26 cases (`baseline-report.md`: 100% assertion/constraint/identifier preservation, eligible median reductions `45.95%` prompt, `69.48%` log, `25.55%` conversation, `16.66%` repository, `15.09%` api, `p95 <= 5.69 ms`).
  - `benchmarks/evaluation/paired_evaluator.py` verifies 21 paired cases offline (`15.78%` eligible median reduction, `0` objective degradations, `0` negative-savings accepted) and confirms `allow_ai_semantic_compression=False` and `pgvector` deferred remain safe defaults. Live commercial LLM grading requires user-supplied provider API keys.
- Next scheduled review: **2027-02-18**.
