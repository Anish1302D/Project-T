# ADR-0003: Local Runtime Transport and Authentication

- **Status:** Accepted
- **Date:** 2026-11-18
- **Review Date:** 2027-02-18
- **Owners:** Project T Architecture
- **Related Master Doc Sections:** Sections 5, 12, 17

---

## Context

The Local Runtime executes on the user's workstation and exposes optimization, token counting, context selection, settings, and metrics APIs to local integrations (VS Code extension, Chrome extension, local MCP server, CLI/scripts).

Because any local process or malicious webpage in a user's browser could attempt to connect to a localhost port (DNS rebinding, CSRF, or cross-origin localhost abuse), unauthenticated localhost HTTP services are a well-known security liability. At the same time, browser extensions (Manifest V3) and VS Code extensions communicate naturally over `fetch`/HTTP to localhost, whereas native messaging alone requires per-browser native host manifests and complicates shared access across VS Code, MCP, and local tooling.

## Decision

1. **Transport & Binding:** Expose the Local Runtime API over HTTP on loopback interface only:
   - Default bind address: `127.0.0.1:4765` (base path `/api/v1`).
   - Binding to `0.0.0.0` is strictly prohibited by default.
2. **Authentication:**
   - Generate a cryptographically random per-installation bearer authentication token at initialization.
   - Store the token in the operating system credential store where supported (with secure local fallback permissions `0600`/ACL-restricted file only when OS keyring is unavailable).
   - Require authentication on all state-changing and optimization endpoints (`POST`, `PUT`, and sensitive `GET` endpoints like `/metrics` and `/settings`). Keep `/api/v1/health` minimal (status/version only, no secrets or user data).
3. **Origin & CORS Enforcement:**
   - Restrict CORS strictly to configured explicit extension origins (e.g., `chrome-extension://<id>`) and authorized local clients. Wildcard `*` CORS is prohibited.
   - Validate `Origin` / `Host` headers on state-changing requests to defeat DNS rebinding and browser CSRF attacks.
4. **Operational Safeguards:**
   - Enforce strict request-body size limits, per-request execution timeouts, and local rate limiting.
   - Require explicit user confirmation for sensitive workspace operations (e.g., scanning or indexing new workspace directories).

## Alternatives Considered

### Option A: Unauthenticated `http://127.0.0.1:4765`
- **Pros:** Zero setup friction for local extensions.
- **Cons:** Vulnerable to any browser tab or untrusted local script triggering optimizations, reading metrics, mutating settings, or exhausting local CPU/token quotas.
- **Why rejected:** Fails Section 5.3 and Section 17 threat model requirements ("Localhost abuse").

### Option B: Unix domain sockets / Windows named pipes only
- **Pros:** Eliminates TCP port scanning and browser XHR access completely.
- **Cons:** Chrome Manifest V3 extensions cannot connect directly to Unix sockets or named pipes without an extra Native Messaging host shim, complicating cross-platform support and unified local API testing.
- **Why rejected:** HTTP on `127.0.0.1` with bearer token + strict CORS + `Host`/`Origin` validation supports Chrome MV3, VS Code, MCP, and `curl`/API tooling uniformly. (Native Messaging remains an optional pairing mechanism to securely provision the token to the Chrome extension.)

### Option C: Self-signed HTTPS on localhost
- **Pros:** Encrypts loopback traffic in transit.
- **Cons:** Self-signed local root CA installation causes frequent browser trust warnings and certificate UX issues in Manifest V3 extensions.
- **Why rejected:** Loopback traffic does not traverse the network; HTTP on `127.0.0.1` with bearer auth avoids brittle local CA trust management for MVP v0.1–v0.4.

## Consequences

### Positive
- Unified local HTTP transport across VS Code, Chrome, MCP, and developer tools.
- Strong protection against cross-origin localhost abuse, DNS rebinding, and unauthenticated local mutation.
- Zero external network exposure by default.

### Negative / Trade-offs
- Browser extension and VS Code extension require an explicit pairing/token-loading step (e.g., copying or securely provisioning the local installation token into extension session/local config, without ever bundling static tokens or cloud API keys).

### Risks & Mitigations
- **Risk:** Token leaked in logs or error stack traces.
  - **Mitigation:** Middleware strips `Authorization` headers before error reporting/logging; bearer token is never logged.
- **Risk:** Port `4765` collision on a developer machine.
  - **Mitigation:** Support explicit port override via local runtime configuration while keeping `127.0.0.1:4765` as the default.

## Review Triggers

- Review on **2027-02-18** or when implementing Chrome extension pairing in MVP v0.3 (evaluate whether a Chrome Native Messaging bridge should automate token handoff).
