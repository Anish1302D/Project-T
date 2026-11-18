# ADR-0011: Privacy, Telemetry, Retention, and Content Storage

- **Status:** Accepted
- **Date:** 2026-11-18
- **Review Date:** 2027-02-18
- **Owners:** Project T Architecture
- **Related Master Doc Sections:** Sections 3.8, 11, 17, 20

---

## Context

Users optimizing prompts, proprietary source code, internal API specifications, and terminal stack traces legitimately treat that content as confidential intellectual property. Any accidental upload of raw prompts/code to a remote analytics server, unredacted error logging of request bodies, or misplaced reliance on unsalted hashes for "anonymization" poses high legal, security, and trust risks.

## Decision

1. **Local-First & Zero Implicit Cloud Upload:**
   - All core optimization runs locally by default.
   - Raw prompts, source code, terminal logs, and file contents are **never uploaded** to Project T cloud servers unless the user explicitly enables a feature that requires it (e.g., optional cloud-hosted API gateway or explicit cloud AI-assisted semantic compression).
2. **Metadata-Only Default Storage:**
   - Both local SQLite (`optimization_runs`, `token_metrics`, `cost_metrics`) and optional cloud analytics store **metadata only by default**: run IDs, integration name, provider/model, optimization mode, transformation method names, token counts, accuracy labels, latency, validation pass/fail, and timestamps.
   - Raw content retention locally (e.g., for user-facing optimization history diff inspection) is **disabled by default** or strictly explicit, configurable, local-only, and subject to clear TTL/user deletion controls.
3. **Low-Entropy Hashing Caveat:**
   - Do **not** treat raw cryptographic hashes (e.g., SHA-256 of short prompts or common error lines) as anonymization guarantees for low-entropy content (Section 17). Local deduplication hashes stay scoped locally by project/content version and are not exported as anonymized cloud telemetry.
4. **Secret Redaction & No Request-Body Logging:**
   - Application logs, exception traces, and API gateway telemetry must never log raw request bodies or HTTP `Authorization`/API key headers. Apply deterministic secret redaction (Bearer tokens, API keys, passwords, connection strings) before persisting diagnostics or error summaries.
5. **Opt-In Telemetry & User Retention Controls:**
   - Product telemetry is strictly **opt-in** with transparent documentation of exact fields collected.
   - Users must have clear controls to configure retention periods, inspect local history, and purge stored metrics/fingerprints/history.

## Alternatives Considered

### Option A: Opt-out telemetry & default storage of raw prompts locally and in cloud
- **Pros:** Simplifies debugging and building automatic cross-device prompt history.
- **Cons:** Violates developer privacy expectations, risks leaking secrets/code in cloud logs or backups, and breaches Section 3.8 and Section 17 principles.
- **Why rejected:** Privacy by default is a non-negotiable architectural pillar.

### Option B: Hash prompts with SHA-256 and upload hashes for global cross-user analytics
- **Pros:** Enables global duplicate analysis.
- **Cons:** Short prompts, standard boilerplate, and single-line errors are low-entropy and vulnerable to dictionary/rainbow-table reversal.
- **Why rejected:** Explicitly warned against in Section 17 ("Hashes should not be treated as anonymization guarantees for low-entropy content").

## Consequences

### Positive
- Safe for adoption in security-conscious individual and enterprise developer environments from v0.1.
- Minimizes storage bloat and regulatory/compliance surface area for optional cloud control plane.

### Negative / Trade-offs
- Server-side debugging of optimization quality issues cannot rely on inspecting user prompts automatically; teams must rely on explicit benchmark fixtures, opt-in sanitized bug reports, and local diagnostic logs.

### Risks & Mitigations
- **Risk:** Unhandled FastAPI/Pydantic validation exceptions echo portions of invalid input payloads into log files.
  - **Mitigation:** Install custom FastAPI exception handlers and structured logging filters that strip `input`/`content` fields and redact secret patterns in all error responses and logs.

## Review Triggers

- Review on **2027-02-18** and during Week 10 security audit prior to public MVP release.
