# ADR-0009: MCP Tool Naming and Contracts

- **Status:** Proposed
- **Date:** 2026-11-18
- **Review Date:** 2027-02-18
- **Owners:** Project T Architecture
- **Related Master Doc Sections:** Sections 2, 9.3, 13, 14, 22

---

## Context

Agentic IDEs and AI assistants (such as VS Code Copilot MCP, Claude Desktop, and compatible MCP clients) can invoke external capabilities via the Model Context Protocol (MCP). However, MCP provides tool interoperability only for clients that support MCP and invoke those tools—it does **not** grant universal interception of an IDE's internal model traffic.

Exposing coarse, unconstrained, or side-effect-heavy MCP tools risks prompt injection, arbitrary filesystem/shell execution, unbounded payload processing, or ambiguous privacy boundaries between local processing and optional cloud services.

## Decision

1. **Narrow, Typed MCP Tool Surface (`apps/mcp-server`):**
   Expose exactly the seven cohesive, verb-first `snake_case` tools defined in Section 9.3 using the official MCP SDK:
   - `optimize_prompt`
   - `analyze_context`
   - `compress_terminal_output`
   - `select_relevant_files`
   - `deduplicate_context`
   - `estimate_tokens`
   - `get_optimization_report`
2. **Strict Input & Safety Contracts:**
   - Validate all tool arguments against canonical JSON Schemas (`packages/contracts`) before invoking Local Runtime endpoints.
   - Enforce per-tool input size and file-count limits.
   - Treat all tool input strings, logs, and file contents strictly as **untrusted data**.
   - **Never execute arbitrary shell commands** as part of any optimization tool (e.g., `compress_terminal_output` operates purely on passed text, never executes commands).
3. **Output Structure, Reversibility, and Provenance:**
   - Return structured JSON results alongside human-readable summary fields, explicit `warnings[]`, `accuracy` (`"exact" | "estimated"`), `methods[]`, and reversible identifiers (`request_id`, recoverable original content/hash policy).
4. **Explicit Local vs. Cloud Labeling:**
   - Every tool's MCP description and documentation must explicitly disclose whether it operates strictly locally (`local-only`) or may invoke external provider/cloud endpoints when optional features (like remote token counting or AI-assisted semantic compression) are enabled. Default behavior for all 7 tools is `local-only`.

## Alternatives Considered

### Option A: Single monolithic `optimize` MCP tool with polymorphic `action` flag
- **Pros:** Fewer tool definitions in client context.
- **Cons:** Weak JSON Schema validation per capability, ambiguous descriptions for LLM tool selection, and awkward argument shapes mixing file paths with terminal logs.
- **Why rejected:** Narrow, single-purpose typed contracts are easier for models to invoke reliably and safer to constrain with per-tool limits.

### Option B: Give MCP server an auto-run shell/command execution tool to capture terminal output
- **Pros:** Agents wouldn't need to pass terminal output explicitly.
- **Cons:** Huge command-injection attack surface and duplicates capabilities already governed by host IDEs.
- **Why rejected:** Explicitly prohibited by Section 9.3 ("Do not execute arbitrary shell commands as part of optimization").

## Consequences

### Positive
- Clean alignment between MCP tool names and Local Runtime `/api/v1` endpoints (`/optimize`, `/analyze`, `/logs/compress`, `/context/select`, `/count`, `/metrics`).
- Clear safety guarantees against prompt/tool injection and unintended shell execution.
- Predictable behavior for compatible MCP hosts.

### Negative / Trade-offs
- Users/agents must explicitly call (or configure rules to call) Project T MCP tools; MCP cannot silently intercept third-party IDE chat traffic.
- Compatibility with specific IDEs (VS Code, Cursor, Windsurf, Antigravity) must be verified empirically against current MCP client implementations before advertising support (Section 2).

### Risks & Mitigations
- **Risk:** `select_relevant_files` attempts to read files outside the authorized workspace root via path traversal (`../`).
  - **Mitigation:** Canonicalize paths, restrict traversal strictly to explicitly configured/approved workspace roots, and respect `.gitignore`/ignore rules.

## Review Triggers

- Review on **2027-02-18** during Week 6 (MCP Server & VS Code MCP workflow validation).
