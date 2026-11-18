# ADR-0007: Protected-Span and Constraint-Preservation Strategy

- **Status:** Accepted
- **Date:** 2026-11-18
- **Review Date:** 2027-02-18
- **Owners:** Project T Architecture
- **Related Master Doc Sections:** Sections 3, 6.3, 7.3, 7.4, 9.4, 16

---

## Context

Token optimizers frequently fail users in subtle, destructive ways: renaming or abbreviating a function symbol, stripping a negative constraint like *"Do not change the database schema"*, altering a JSON key, collapsing a file path or line reference, or paraphrasing an exact error string. Once an identifier or constraint is corrupted, the downstream LLM produces broken code or violates explicit user boundaries.

Optimization modes (`safe`, `balanced`, `aggressive`) allow different levels of compression risk, **but** Section 6.3 strictly mandates that no mode may override hard preservation rules.

## Decision

1. **Pre-Transformation Span Locking & Constraint Extraction:**
   - Before any deduplication or compression transformation runs, extract:
     - **Explicit constraints & prohibitions** (e.g., *"Do not..."*, *"Must..."*, *"Only modify..."*, output format requirements).
     - **Protected spans** across all 10 protected categories defined in Section 7.4:
       1. Function, class, and variable names (`preserve_identifiers` flag + automatic AST/regex symbol detection).
       2. Imports and type definitions.
       3. API endpoints and HTTP methods.
       4. Error codes and exact error messages when relevant.
       5. File paths and line references.
       6. JSON keys and schema requirements.
       7. Explicit user constraints and prohibitions.
       8. Tool names and tool arguments.
       9. Version numbers and configuration values.
       10. User-specified output formats.
2. **Immutable Placeholder / Span-Masking Mechanism:**
   - Replace or lock protected spans during rule-based or semantic rewriting via immutable sentinel tokens / span ranges so transformations can operate around them without mutating inside them.
   - Never silently alter tool schemas, function arguments, JSON contracts, or structured-output requirements (Section 9.4).
3. **Post-Transformation Hard Verification:**
   - The `QualityValidator` verifies exact retention of every locked identifier, path, JSON key, version literal, and extracted constraint after optimization.
   - Any missing, altered, or reordered critical constraint causes immediate validation failure (`validation.passed = false`) and automatic fallback to the original input.
4. **Mode-Invariant Hard Rules:**
   - `safe`, `balanced`, and `aggressive` modes adjust surrounding prose/redundancy aggressiveness only; hard preservation invariants remain enforced across all three modes.

## Alternatives Considered

### Option A: Post-hoc LLM judge only to check if constraints survived
- **Pros:** Can detect paraphrased semantic changes.
- **Cons:** Non-deterministic, slow, costly, cannot run offline, and fails silently on subtle identifier typos (`user_id` vs `userId`).
- **Why rejected:** Deterministic exact span locking + deterministic invariant verification is required for 100% pass rate targets on curated constraint/identifier benchmarks (Section 16).

### Option B: Allow `aggressive` mode to paraphrase identifiers or relax constraint checks
- **Pros:** Higher raw token reduction on dense technical text.
- **Cons:** High task failure rate in coding and tool-calling workflows.
- **Why rejected:** Explicitly forbidden by Section 6.3 ("The mode must not override hard preservation rules").

## Consequences

### Positive
- Guarantees 100% deterministic preservation of detected symbols, paths, schemas, and explicit constraints on validated inputs.
- Makes transformations explainable: reports can highlight exactly which constraints and protected spans were detected and locked.

### Negative / Trade-offs
- Inputs densely packed with identifiers, file paths, and JSON schemas will yield lower compression percentages than pure natural-language prose (expected and desirable behavior).
- Natural-language constraint extraction regexes/parsers require careful benchmark tuning to minimize false negatives (missed constraints) and avoid over-locking ordinary prose.

### Risks & Mitigations
- **Risk:** Novel phrasing of negative constraints misses heuristic extractor patterns.
  - **Mitigation:** Build a dedicated curated **Constraint Benchmark** suite (`benchmarks/`) and expand extractor patterns before enabling aggressive prose compression.

## Review Triggers

- Review on **2027-02-18** against Milestone 1 Constraint and Identifier benchmark suites (target: 100% preservation on curated test fixtures).
