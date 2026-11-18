# Token Accounting and Quality Scoring

**Master Reference:** Sections 7.8, 7.9, 8, 16, and 21 of [token-optimization-platform-architecture.md](../token-optimization-platform-architecture.md).  
**Related ADRs:** [ADR-0005](../decisions/ADR-0005-tokenizer-adapter-and-accuracy-labeling.md), [ADR-0007](../decisions/ADR-0007-protected-spans-and-constraint-preservation.md), [ADR-0012](../decisions/ADR-0012-benchmark-methodology-and-release-criteria.md).

---

## 1. Token Savings Formula

Matching Section 7.8:

$$\text{Savings \%} = \frac{\text{Original tokens} - \text{Optimized tokens}}{\text{Original tokens}} \times 100$$

### Edge & Accounting Rules
- If `Original tokens == 0`, `Savings % = 0.0`.
- Every calculation records `accuracy: "exact" | "estimated"` from the `TokenizerAdapter`.
- **Never** present `"estimated"` local token savings as provider-confirmed savings.
- **Never** present token reduction percentages alone as guaranteed dollar savings without versioned pricing and provider usage reconciliation (e.g., prompt-cache behavior).

---

## 2. Diagnostic Quality Score (`Q`)

Matching Section 7.9, the engine computes a provisional internal diagnostic score combining four normalized components in $[0, 1]$:

$$Q = 0.35I + 0.25C + 0.20S + 0.20R$$

Where:
- $I \in [0, 1]$: **Intent preservation** (retention of primary task objective and action verbs).
- $C \in [0, 1]$: **Constraint preservation** (ratio of extracted prohibitions, mandates, and boundary clauses preserved intact).
- $S \in [0, 1]$: **Structural preservation** (retention of JSON validity, Markdown code blocks, heading hierarchy, or list structure).
- $R \in [0, 1]$: **Reference and identifier preservation** (ratio of locked code symbols, file paths, line numbers, endpoints, error codes, and version literals preserved verbatim).

> **Critical Warning (Section 7.9 & Section 16):**  
> $Q$ is an **internal diagnostic metric only** — it is **NOT** proof of semantic equivalence or downstream model task success. Paired LLM task-completion benchmarks and human review are mandatory to validate optimization quality.

---

## 3. Hard Quality Validator Gate (`validation/`)

Unlike the composite diagnostic score $Q$, the **QualityValidator** enforces binary hard invariants before allowing any optimized candidate to leave the pipeline:

| Check | Requirement | Action on Failure |
|---|---|---|
| `constraints_preserved` | $C == 1.0$ (every extracted explicit prohibition/mandate retained) | Reject candidate -> fallback to original |
| `identifiers_preserved` | $R == 1.0$ when `preserve_identifiers == true` (every locked symbol/path/version/endpoint intact) | Reject candidate -> fallback to original |
| `structure_preserved` | Valid JSON remains parseable with identical keys; fenced code blocks balanced; tool/schema blocks unmodified | Reject candidate -> fallback to original |
| `positive_savings` | `optimized_tokens < original_tokens` and `tokens_saved >= min_meaningful_savings` | Return original (`fallback_no_savings`) |
