# Integration Architecture

**Master Reference:** Sections 1, 2, 9, 13, 14, and 22 of [token-optimization-platform-architecture.md](../token-optimization-platform-architecture.md).  
**Related ADRs:** [ADR-0002](../decisions/ADR-0002-python-engine-and-typescript-integrations.md), [ADR-0009](../decisions/ADR-0009-mcp-tool-naming-and-contracts.md), [ADR-0010](../decisions/ADR-0010-browser-permissions-and-site-adapters.md).

---

## 1. Honest Integration Boundaries

Project T explicitly rejects misleading claims about universal interception. Each integration operates strictly within the official interfaces and security boundaries of its host environment:

| Integration | What It Can Access | What It Cannot Assume / Claim |
|---|---|---|
| **Browser Extension** | Prompt text explicitly selected or submitted by the user in supported AI web UIs | No access to hidden server-side context, private internal API requests, cookies, or passwords |
| **VS Code Extension** | Editor selection, workspace files approved by user, selected terminal output, own language-model tools | Cannot transparently rewrite all HTTP requests from arbitrary third-party AI extensions |
| **MCP Server** | Typed tool arguments passed explicitly by an MCP-compatible host/agent | Does not grant universal access to an IDE's internal model traffic |
| **API Gateway** | Requests explicitly routed by an application to the gateway endpoint | Cannot optimize direct calls that bypass the gateway |
| **Other IDEs (Antigravity, Cursor, Windsurf)** | Standard MCP / compatible extension APIs once validated | Must not be advertised as supported until tested against current extension & MCP interfaces |

---

## 2. Browser Extension (`apps/browser-extension`)

- **Stack:** TypeScript, React, Tailwind CSS (`shared-ui`), Chrome Manifest V3.
- **Structure:** `src/background/`, `src/content/`, `src/popup/`, `src/options/`, `src/integrations/`.

### Data Flow
```text
Supported AI Website (ChatGPT / Claude / Gemini)
    -> User action (button click / shortcut) on prompt input field
    -> Content script invokes SiteAdapter prompt extractor
    -> Extension background service worker
    -> Authenticated HTTP call to Local Runtime (127.0.0.1:4765/api/v1/optimize)
    -> OptimizationResult returned to UI overlay/popup
    -> User inspects diff, token delta, and accuracy badge
    -> User clicks Accept (injects optimized text) or Reject / Restore Original
    -> User submits prompt normally
```

### MVP Capabilities & Guardrails
- Site-specific adapters (`integrations/`) behind a common `SiteAdapter` interface.
- Minimal Manifest V3 host permissions restricted to supported AI domains and `127.0.0.1`.
- Zero collection of passwords, cookies, unrelated pages, or background conversations.
- No API keys stored in extension bundles.

---

## 3. VS Code Extension (`apps/vscode-extension`)

- **Stack:** TypeScript + VS Code Extension API.
- **Structure:** `src/commands/`, `src/providers/`, `src/views/`, `src/context/`, `src/terminal/`, `src/runtime/`.

### MVP Capabilities (v0.2)
1. **Optimize Selected Text:** Send editor selection to `/api/v1/optimize` and show inline/side-by-side before-and-after diff preview before applying.
2. **Analyze Context / Prompt:** Call `/api/v1/analyze` to inspect detected content type, constraints, protected spans, and estimated tokens.
3. **Workspace File Relevance Analysis:** Call `/api/v1/context/select` (with explicit workspace scope) to rank task-relevant files and tests via BM25/dependency cues.
4. **Terminal Output Compression:** Compress user-selected terminal output via `/api/v1/logs/compress` while retaining original output recovery.
5. **Runtime Health & Connection Panel:** Monitor `GET /api/v1/health`, configure runtime port/token safely via VS Code `SecretStorage`.
6. **Optimization History View:** Local run metrics and diffs (respecting metadata-only defaults unless user opts into local diff retention).

### Later Features
- Native VS Code Language Model Tools integration (where supported by VS Code AI Extensibility API).
- Bundled MCP client/server registration workflow.
- Agent context-pack generation.
- Project profile & freshness-aware context memory UI.

---

## 4. MCP Server (`apps/mcp-server`)

- **Stack:** TypeScript + Official MCP SDK (`src/server.ts`, `src/tools/`, `src/resources/`).
- **Exposed Tools:** `optimize_prompt`, `analyze_context`, `compress_terminal_output`, `select_relevant_files`, `deduplicate_context`, `estimate_tokens`, `get_optimization_report`.
- **Full specification:** See [MCP Tools Specification](../api/mcp-tools-specification.md).

---

## 5. API Gateway (`apps/api-gateway`)

- **Stack:** Python 3.12+ / FastAPI (`src/routes/`, `src/middleware/`, `src/providers/`, `src/streaming/`, `src/usage/`).
- **Capabilities:** Request normalization across OpenAI/Anthropic/Google schemas, optimization preflight, SSE/streaming pass-through, provider response usage reconciliation, versioned pricing attribution, optional bypass header/flag, idempotency, and redacted logging.
- **Strict invariant:** Never silently alter tool schemas, function arguments, JSON contracts, or structured-output constraints.
- **Full specification:** See [API Gateway Specification](../api/api-gateway-specification.md).

---

## 6. Cloud Dashboard (`apps/dashboard`)

- **Stack:** React, Vite, Tailwind CSS (`src/components/`, `src/pages/`, `src/charts/`, `src/hooks/`, `src/services/`).
- **Core Views (MVP v0.5):**
  1. Original vs. optimized token counts.
  2. Net tokens saved (separating `estimated`, `exact`, and `provider-confirmed`).
  3. Estimated cost avoided (computed via versioned pricing metadata).
  4. Provider / model breakdown.
  5. Integration breakdown (VS Code, Browser, MCP, Gateway).
  6. Daily / weekly / monthly trends.
  7. Optimization modes (`safe`, `balanced`, `aggressive`) and methods distribution.
  8. Validation failures and fallback rates.
  9. Quality benchmark summaries.
  10. Optimization latency percentiles.
