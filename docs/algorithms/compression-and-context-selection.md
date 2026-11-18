# Compression and Context Selection

**Master Reference:** Sections 7.1, 7.5, 7.7, 14, and 21 of [token-optimization-platform-architecture.md](../token-optimization-platform-architecture.md).

---

## 1. Whitespace Normalization & Rule-Based Compression (`compression/`)

### Safe Whitespace Normalization (P0)
- Collapse runs of 3+ consecutive blank lines into at most 2 (or 1 in `balanced`/`aggressive` prose).
- Trim trailing spaces per line outside literal/code blocks where trailing whitespace is meaningful.
- Never collapse leading indentation inside `source_code`, YAML, Makefiles, Python snippets, or Markdown fenced blocks.

### Rule-Based Prose Compression (P0)
- Operates strictly on unprotected natural-language spans outside constraints and code/JSON blocks.
- Removes conversational filler and redundant ceremonial phrasing (e.g., *"Could you please help me by taking a look at..."* -> direct imperative preserving task intent).
- Consolidates repetitive instruction lead-ins while verifying via `QualityValidator` that no target, constraint, or format requirement was altered.

---

## 2. Terminal-Output Compression (`compression/`, P0)

Terminal logs and test runner outputs frequently contain thousands of tokens of progress spinners, passing test dots, ANSI color codes, and repetitive dependency install lines.

### Preserved Signals (Section 7.7)
Terminal compression **MUST preserve**:
1. Executed **command** and **exit code**.
2. **First actionable error** (primary failure point).
3. Relevant **stack trace frames** (prioritizing project/user frames over deep third-party framework frames when pruning in `balanced`/`aggressive`).
4. **File paths and line numbers**.
5. **Warnings tied to the failure**.
6. **Relevant lines immediately before and after an error** (configurable `context_lines`, default 5).
7. **Test names and summary counts** (e.g., `142 passed, 2 failed`).

### Safety Requirement
- Strip ANSI escape sequences safely.
- Never discard output lines likely required to diagnose a failure.
- Keep original terminal output recoverable via the returned `OptimizationResult` / UI history control.

---

## 3. Context Selection (`context-selection/`, P0)

For repository and coding workflows (`/context/select`), rank workspace files and snippets against the task description before stuffing prompts with irrelevant code.

### Ranking Signals (Section 7.5)
1. **Task-description lexical relevance:** Start with **BM25 / SQLite FTS5** over normalized file paths, symbols, and content tokens.
2. **File names and paths:** Boost direct path/filename mentions in `task_description`.
3. **Symbol references and imports:** Boost modules defining or importing symbols referenced in the task or primary target files.
4. **Dependency relationships:** Lightweight static import/dependency graph proximity (1-hop neighbors).
5. **Associated test files:** Surface tests corresponding to selected target modules.
6. **Recent changes & freshness:** Boost recently modified files and invalidate stale entries via `file_hash`.
7. **Explicitly pinned files:** Pinned files (`pinned_files[]`) are always retained within budget.

### Deferred Complexity Rule
- **Do NOT introduce embedding models or a vector database in v0.1.** Add embeddings (P2 / optional `pgvector`) **only** if empirical benchmarks on the Repository Benchmark dataset demonstrate significant recall/precision improvement justifying the added indexing and compute cost.

---

## 4. Conversation Compaction & Structured Summarization (P1)

- **Structured Summarization:** Compress known document/log templates (e.g., repetitive build tables, verbose API specs) using deterministic structural condensation.
- **Conversation Compaction:** Summarize older historical turns while explicitly pinning and retaining:
  - Active user goals
  - Agreed architectural/implementation decisions
  - Explicit constraints & prohibitions
  - Unresolved tasks / open errors

---

## 5. Optional AI-Assisted Semantic Compression (P1 / Experimental in v0.1)

- **Off by default.** Executed **only** if:
  1. Explicitly enabled in request options and user settings (`allow_ai_semantic_compression = true`).
  2. Policy mode allows it (`balanced` or `aggressive`, never `safe`).
  3. Deterministic steps have already run and remaining payload size exceeds a minimum benefit threshold where expected token savings outweigh LLM compression latency and cost.
- Subject to the exact same protected-span locking and post-hoc `QualityValidator` gate as deterministic passes.
