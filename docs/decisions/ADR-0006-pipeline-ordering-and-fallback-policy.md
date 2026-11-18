# ADR-0006: Optimization Pipeline Ordering and Fallback Policy

- **Status:** Accepted
- **Date:** 2026-11-18
- **Review Date:** 2027-02-18
- **Owners:** Project T Architecture
- **Related Master Doc Sections:** Sections 3, 6, 7, 14, 20

---

## Context

Applying transformations in an arbitrary order—or running expensive LLM-based semantic rewriting before eliminating obvious formatting noise and exact duplicates—wastes compute, increases latency, and risks corrupting protected constraints or structured code before validation can catch regressions.

Similarly, an optimizer that emits degraded prompts or outputs with negligible/negative token savings violates the core product promise ("spend fewer tokens accomplishing the same work").

## Decision

1. **Fixed Deterministic-First Pipeline Order:**
   Execute every optimization request through the ordered pipeline defined in Section 6.2:
   1. **Classify Content** (`ContentType` + metadata).
   2. **Measure Baseline Tokens** (via `TokenizerAdapter`).
   3. **Extract Constraints and Protected Spans** (hard lock before mutation).
   4. **Detect Redundancy** (exact deduplication, staged near-duplicate candidates where permitted).
   5. **Apply Safe Deterministic Rules** (safe whitespace normalization, filler/rule-based compression, terminal log filtering where applicable).
   6. **Select Relevant Context** (BM25/SQLite FTS ranking for multi-file/context inputs).
   7. **Optional AI-Assisted Semantic Compression** (only if explicitly enabled by policy/mode, allowed by privacy settings, and expected benefit justifies cost/latency).
   8. **Build Candidate** and record reversible transformation metadata.
   9. **Validate Quality** (constraints, protected identifiers, structural integrity, references).
   10. **Measure Candidate Tokens & Compute Savings**.
2. **Strict Fail-Safe Fallback Policy:**
   Return the **unmodified original content** (with diagnostic warnings and recorded methods/status) whenever any of the following occur:
   - Quality validation fails (any protected constraint, identifier, or structural invariant broken).
   - Savings are zero, negative, or below the configured meaningful savings threshold (configurable minimum, avoiding churn for trivial 1–2 token deltas).
   - Any unexpected stage error or execution timeout occurs.
3. **Reversibility:**
   Always return `original_content` alongside `optimized_content` (or retain reversible references in client UI state) so users can inspect diffs and restore the original immediately.

## Alternatives Considered

### Option A: AI-assisted semantic compression first, deterministic cleanup second
- **Pros:** Potentially high compression ratio on verbose prose.
- **Cons:** Expensive, slow (>100 ms), sends data to an LLM even when simple deduplication/whitespace removal suffices, and risks hallucinating or dropping identifiers before extraction.
- **Why rejected:** Violates Deterministic-First (Section 3.3) and Local-First latency targets.

### Option B: Best-effort partial output on validation failure
- **Pros:** Might still save some tokens if only one minor constraint check is uncertain.
- **Cons:** Risky; silently shipping damaged instructions or mangled symbol names breaks user tasks and destroys trust.
- **Why rejected:** Violates Fail-Safe principle (Section 3.7) and Quality-Aware principle (Section 3.4).

## Consequences

### Positive
- Deterministic steps handle the majority of safe savings quickly (`< 100 ms` target for small inputs) and offline.
- Extracting constraints and protected spans *before* transformation guarantees downstream compressors know what cannot be touched.
- Zero regression guarantee against broken validation or negative savings via automatic fallback to original input.

### Negative / Trade-offs
- Pipeline latency includes baseline + candidate token counting plus validation pass; for very tiny inputs (<20 tokens), meaningful-savings threshold will routinely skip modification and return original.

### Risks & Mitigations
- **Risk:** Individual optimization modules tightly couple to each other's internal data structures.
  - **Mitigation:** Enforce an immutable/versioned internal `PipelineContext` state passed cleanly through the `PipelineOrchestrator`, keeping each stage independently unit-testable.

## Review Triggers

- Review on **2027-02-18** after Milestone 1 benchmarks establish per-stage latency and minimum meaningful-savings thresholds across `Safe`, `Balanced`, and `Aggressive` modes.
