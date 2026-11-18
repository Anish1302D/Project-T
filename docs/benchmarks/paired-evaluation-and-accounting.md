# Paired Evaluation Protocol and Token/Cost Accounting

**Master Reference:** Sections 7.8, 7.9, and 16 of [token-optimization-platform-architecture.md](../token-optimization-platform-architecture.md).  
**Related ADRs:** [ADR-0005](../decisions/ADR-0005-tokenizer-adapter-and-accuracy-labeling.md), [ADR-0012](../decisions/ADR-0012-benchmark-methodology-and-release-criteria.md).

---

## 1. Paired Evaluation Protocol

Internal quality heuristics (`Q = 0.35I + 0.25C + 0.20S + 0.20R`) are diagnostic signals only and **never** sufficient proof of task-completion parity. Downstream equivalence requires paired evaluation:

1. **Control run (Baseline):** Submit the original unmodified prompt/context to a **fixed model and version**.
2. **Treatment run (Optimized):** Submit the optimized prompt/context to the **exact same fixed model and version**.
3. **Controlled environment:** Keep task definition, available tools, system settings, and sampling parameters (temperature, seed, max tokens) strictly identical between control and treatment.
4. **Objective verification:** Grade outputs using automated assertions (unit tests, compiler/linter pass, JSON schema validation, exact target edits).
5. **Human review:** Conduct blinded human evaluation for subjective or open-ended prompt tasks.
6. **Dataset scale:** Repeat across the representative benchmark dataset for statistical confidence.
7. **Transparent reporting:** Report all task failures, constraint violations, and negative-savings fallback cases alongside reductions.
8. **Independence rule:** Never treat the optimizer's own `quality_score` as sole proof of model-level quality preservation.

---

## 2. Token & Cost Accounting Distinctions

Project T strictly separates three measurement tiers across APIs, databases (`token_metrics`, `cost_metrics`), benchmarks, and dashboard views:

| Term | Source of Truth | Labeling Requirement | Can Equate Directly to Dollars? |
|---|---|---|---|
| **Estimated savings** | Local heuristic estimator or non-authoritative local approximation | Must be labeled `accuracy: "estimated"` | **No** — informational estimate only |
| **Exact pre-flight count** | Authoritative model-specific tokenizer or provider counting endpoint | Labeled `accuracy: "exact"` | Only as pre-flight estimate; actual billing can still vary with caching/framing |
| **Provider-confirmed savings** | Upstream provider API usage response (`provider_confirmed_input_tokens`) compared against paired baseline | Marked provider-confirmed in `token_metrics` & gateway logs | Basis for billing reconciliation |
| **Cost avoided** | Versioned model pricing metadata applied to confirmed billable input usage (accounting for cached tokens & any optional semantic-compression LLM cost) | Tagged with `pricing_version` in `cost_metrics` | Yes, when reconciled against applicable versioned pricing & billing behavior |

> **Core Accounting Rule (Section 16):**  
> *Do not equate token reduction with cost reduction unless provider pricing and billing behavior confirm it.* (For instance, prompt caching hits or semantic-compression LLM invocation costs can offset naive input-token reductions.)
