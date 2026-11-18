# Security Architecture

**Master Reference:** Sections 5.3, 9, and 17 of [token-optimization-platform-architecture.md](../token-optimization-platform-architecture.md).  
**Related ADRs:** [ADR-0003](../decisions/ADR-0003-local-runtime-transport-and-auth.md), [ADR-0009](../decisions/ADR-0009-mcp-tool-naming-and-contracts.md), [ADR-0010](../decisions/ADR-0010-browser-permissions-and-site-adapters.md).

---

## 1. Core Security Principles

1. **Local processing by default:** Code, prompts, and terminal output remain on the user's machine unless an explicitly enabled feature requires cloud access.
2. **Authenticated loopback runtime:** Local Runtime binds strictly to `127.0.0.1:4765` (never `0.0.0.0`) and requires per-installation bearer authentication.
3. **Zero secrets in frontends:** Never place upstream provider API keys or cloud database credentials inside browser extension bundles or dashboard frontend assets.
4. **Least-privilege host integrations:** Minimal host permissions for Chrome Manifest V3; explicit workspace root approval for IDE/MCP file access.
5. **Untrusted input boundary:** Treat every prompt, source file, terminal log, and MCP tool argument strictly as untrusted data.

---

## 2. Local Runtime Controls (`apps/local-runtime`)

| Control | Implementation Requirement |
|---|---|
| **Installation token** | Generated via CSPRNG on first boot; stored in OS credential store where supported (`0600` ACL file fallback if unavailable) |
| **Network binding** | Loopback `127.0.0.1:4765` only; startup validation fails if unsafe default public binding is attempted without explicit override |
| **CORS & Origin validation** | Strict allowlist of extension IDs (`chrome-extension://<id>`) and authorized local clients; no `*` wildcard; validate `Origin` and `Host` headers to stop DNS rebinding & CSRF |
| **Payload & execution limits** | Enforce max body size (e.g., 2 MB), execution timeouts, and local sliding-window rate limits |
| **Workspace approval** | Require explicit user consent/allowlist before scanning/indexing a directory via `/context/select` |
| **Sanitized error handlers** | Strip `Authorization` headers, API keys, and request `content` from HTTP error payloads and logs |

---

## 3. Integration Security Boundaries

### 3.1 Browser Extension (`apps/browser-extension`)
- Chrome Manifest V3 only; no remote code execution.
- Host permissions restricted solely to supported AI sites (ChatGPT, Claude, Gemini) plus `127.0.0.1`.
- Never read passwords, cookies, unrelated tabs, or hidden background traffic.
- Never store upstream provider API keys in `chrome.storage` or bundled JavaScript.

### 3.2 MCP Server (`apps/mcp-server`)
- Validate every tool call with strict JSON Schema and per-tool byte/item limits.
- Reject relative path escapes (`..` / symlink escapes) outside explicitly authorized workspace roots in `select_relevant_files`.
- **Prohibit shell execution:** Optimization tools operate strictly on provided text/approved read-only context and never invoke subprocess shells.

### 3.3 API Gateway & Cloud Control Plane (`apps/api-gateway`, `services/`)
- Manage upstream provider API keys via OS credential store locally or managed cloud secret stores in hosted deployments.
- Enforce TLS in transit for all cloud/upstream traffic (`HTTPS`).
- Encrypt cloud credentials and sensitive configuration at rest.
- Never silently mutate tool schemas, function arguments, or structured-output contracts during optimization.
