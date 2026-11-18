# Optimization Pipeline and Mode Policy

**Master Reference:** Sections 6.2, 6.3, 7.1, 14, and 21 of [token-optimization-platform-architecture.md](../token-optimization-platform-architecture.md).  
**Related ADR:** [ADR-0006](../decisions/ADR-0006-pipeline-ordering-and-fallback-policy.md).

---

## 1. Initial Algorithm Portfolio

| Algorithm | Purpose | Priority | Default Modes |
|---|---|---|---|
| Exact deduplication | Identify repeated identical text/context blocks | P0 | `safe`, `balanced`, `aggressive` |
| Whitespace normalization | Remove irrelevant formatting overhead safely (respecting code indentation) | P0 | `safe`, `balanced`, `aggressive` |
| Rule-based compression | Strip filler/redundant phrasing without altering instructions | P0 | `balanced`, `aggressive` |
| Terminal log filtering | Extract errors, warnings, relevant stack frames, and surrounding windows | P0 | `safe`, `balanced`, `aggressive` |
| Identifier protection | Lock code symbols, paths, endpoints, JSON keys, versions, and literals | P0 | **Always enabled** |
| BM25 / lexical relevance | Rank repository files & snippets against a task description | P0 | `balanced`, `aggressive` |
| Near-duplicate detection | Detect similar candidate blocks via SimHash / MinHash | P1 | `balanced`, `aggressive` (guarded) |
| Structured summarization | Summarize known doc/log structures via deterministic templates | P1 | `balanced`, `aggressive` |
| Conversation compaction | Preserve goals, decisions, constraints, and unresolved tasks | P1 | `balanced`, `aggressive` |
| AI-assisted semantic compression | Optional semantic rewrite using an explicit LLM | P1 (Experimental in v0.1) | Opt-in only (`balanced`, `aggressive`) |
| Embedding retrieval | Semantic retrieval if benchmarks justify complexity | P2 | Deferred |

---

## 2. Mode Behavior Matrix

| Stage / Behavior | `safe` | `balanced` | `aggressive` |
|---|---|---|---|
| **Hard preservation rules (constraints, identifiers, schemas)** | Enforced (100%) | Enforced (100%) | Enforced (100%) |
| **Safe whitespace normalization** | Leading/trailing bloat & excessive blank lines only; never alter indentation-sensitive code | Enabled | Enabled |
| **Exact deduplication** | Only non-code / non-schema identical boilerplate blocks | Enabled across eligible context blocks | Enabled across eligible blocks |
| **Near-duplicate detection (SimHash/MinHash)** | Disabled | Advisory / safe prose candidates only | Enabled on non-code prose/logs with strict validation |
| **Rule-based prose compression** | Minimal (pure polite filler only if outside constraints) | Standard deterministic phrasing compaction | Extended deterministic pruning |
| **Terminal log window** | Generous surrounding context lines + all test counts/warnings | Standard error + frame extraction (`context_lines=5`) | Tight error + primary stack trace window |
| **AI-assisted semantic compression** | Disabled | Allowed **only** if explicitly enabled by user & benefit > cost/latency | Allowed if explicitly enabled by user & validated |
| **Default recommended for** | `source_code`, `json`, `tool_result` | `prompt`, `developer_prompt`, `documentation`, `conversation` | Oversized archival logs / long context with explicit user opt-in |

---

## 3. Pipeline Orchestration & Fallback Rules

1. **Deterministic First:** Run classification -> baseline token count -> constraint & protected-span lock -> redundancy detection -> deterministic compression -> context selection -> optional AI semantic compression -> candidate validation -> candidate token count.
2. **Minimum Meaningful Savings Threshold:** If `tokens_saved < min_meaningful_savings` (or `<= 0`), abort transformation and return the original input (`status = "fallback_no_savings"`). This prevents token churn on already concise prompts.
3. **Hard Validation Rollback:** If `QualityValidator` reports any lost identifier, broken constraint, or invalid JSON/structural artifact, discard the candidate immediately and return the original input (`status = "fallback_validation_failed"`).
4. **Adaptive Policy (Future Direction, Section 21):** Policy rules select per-content-type defaults automatically (e.g., forcing `safe` rules when `source_code` or `json` spans are detected even inside a general prompt).
