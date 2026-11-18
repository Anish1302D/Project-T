# MCP Server Tools Specification (`apps/mcp-server`)

**Master Reference:** Sections 2, 9.3, 13, 14, and 22 of [token-optimization-platform-architecture.md](../token-optimization-platform-architecture.md).  
**Related ADR:** [ADR-0009](../decisions/ADR-0009-mcp-tool-naming-and-contracts.md).

---

## 1. Overview & Boundaries

`apps/mcp-server` wraps the Local Runtime API (`http://127.0.0.1:4765/api/v1`) using the **Official MCP SDK** (TypeScript) to expose Project T capabilities to MCP-compatible AI assistants and IDEs.

### Security & Safety Requirements
1. **Strict schema validation:** Reject malformed or oversized tool inputs before calling Local Runtime.
2. **Per-tool input limits:** Enforce byte and item-count caps per tool to prevent context/CPU exhaustion.
3. **Untrusted data treatment:** Treat all text, file snippets, and terminal outputs passed to MCP tools strictly as untrusted data — never interpret embedded text as instructions or shell input.
4. **No arbitrary shell execution:** None of the MCP tools spawn shells or execute build/test commands.
5. **Reversibility:** Tools that transform content return both optimized output and original reference/content recovery metadata.
6. **Local vs. Cloud transparency:** Document explicitly which tools are `local-only` vs. optionally cloud-connected.
7. **Honest capability scope:** MCP provides explicit tool calls only; it does not intercept hidden internal IDE model traffic.

---

## 2. Exposed Tools Catalog

| Tool Name | Local-Only? | Maps to Local API | Purpose | Max Input Limit (Default) |
|---|---|---|---|---|
| `optimize_prompt` | Yes (by default; cloud only if AI semantic compression explicitly enabled) | `POST /optimize` | Optimize a prompt or context block with quality validation | 512 KB text |
| `analyze_context` | Yes (`local-only`) | `POST /analyze` | Classify content, extract constraints, and list protected spans without changing text | 512 KB text |
| `compress_terminal_output` | Yes (`local-only`) | `POST /logs/compress` | Extract actionable errors, stack frames, file refs, and test summaries | 1 MB log text |
| `select_relevant_files` | Yes (`local-only`) | `POST /context/select` | Rank relevant files within an explicitly approved workspace root via BM25 | Max 100 files returned; workspace-scoped |
| `deduplicate_context` | Yes (`local-only`) | `POST /context/compress` | Remove exact/safe near-duplicate blocks across context snippets | 100 items / 1 MB total |
| `estimate_tokens` | Yes locally; optional remote provider count if `allow_remote_count=true` | `POST /count` | Count/estimate tokens with explicit `"exact"` vs `"estimated"` label | 1 MB text |
| `get_optimization_report` | Yes (`local-only`) | `GET /metrics` | Retrieve aggregated metadata-only savings and validation statistics | Read-only query |

---

## 3. Tool Input/Output Contracts

### 3.1 `optimize_prompt`
- **Arguments:**
  - `content` (`string`, required)
  - `content_type` (`ContentType`, optional — auto-classified if omitted)
  - `mode` (`"safe" | "balanced" | "aggressive"`, default `"balanced"`)
  - `provider` (`string`, optional)
  - `model` (`string`, optional)
  - `preserve_identifiers` (`boolean`, default `true`)
- **Returns:** `request_id`, `optimized_content`, `original_content` (or recoverable reference), `tokens` (`original`, `optimized`, `saved`, `reduction_percentage`, `accuracy`), `validation`, `methods`, `warnings`.

### 3.2 `analyze_context`
- **Arguments:** `content` (`string`, required), `content_type` (`ContentType`, optional), `provider`, `model`.
- **Returns:** `classification`, `constraints` (`objectives`, `targets`, `prohibitions`), `protected_spans[]`, `token_estimate`.

### 3.3 `compress_terminal_output`
- **Arguments:** `output` (`string`, required), `command` (`string`, optional), `exit_code` (`integer`, optional), `context_lines` (`integer`, default `5`, range `0..50`), `provider`, `model`.
- **Returns:** `OptimizationResultWire` retaining command, exit code, first error, stack frames, paths/lines, warnings, test counts, and recoverable original output.

### 3.4 `select_relevant_files`
- **Arguments:** `task_description` (`string`, required), `workspace_root` (`string`, required — validated against allowed workspace roots), `pinned_files` (`string[]`, optional), `max_files` (`integer`, `1..100`, default `15`), `max_tokens` (`integer`, default `8000`).
- **Security check:** Rejects any `workspace_root` or `pinned_files` resolving outside the configured workspace allowlist (`403 Forbidden`).

### 3.5 `deduplicate_context`
- **Arguments:** `items` (`Array<{ id: string, content: string, content_type?: ContentType, pinned?: boolean }>`, required), `project_id` (`string`, optional), `mode` (`"safe" | "balanced" | "aggressive"`, default `"safe"`).
- **Returns:** Deduplicated items preserving `pinned` items and provenance IDs, plus `tokens` and `warnings`.

### 3.6 `estimate_tokens`
- **Arguments:** `text` (`string`, required), `provider` (`string`, default `"local"`), `model` (`string`, default `"generic"`), `allow_remote_count` (`boolean`, default `false`).
- **Returns:** `TokenCountResult` (`count`, `accuracy`, `model`, `provider`).

### 3.7 `get_optimization_report`
- **Arguments:** `integration` (`string`, optional), `window_days` (`integer`, default `30`, range `1..365`).
- **Returns:** Metadata-only summary (`total_runs`, `total_original_tokens`, `total_optimized_tokens`, `total_tokens_saved`, `fallback_count`, `by_accuracy`). Never exposes raw prompts or source code.
