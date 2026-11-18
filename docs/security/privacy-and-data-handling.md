# Privacy and Data Handling Policy

**Master Reference:** Sections 3.8, 11, and 17 of [token-optimization-platform-architecture.md](../token-optimization-platform-architecture.md).  
**Related ADR:** [ADR-0011](../decisions/ADR-0011-privacy-telemetry-retention-and-storage.md).

---

## 1. Privacy-by-Default Guarantees

1. **Zero implicit uploads:** Raw prompts, optimized prompts, repository source files, and terminal outputs are processed locally and **never** transmitted to Project T cloud servers unless the user explicitly enables a cloud feature that requires it (e.g., optional cloud gateway or explicit remote semantic compression).
2. **Metadata-only persistence by default:** Local SQLite (`optimization_runs`, `token_metrics`, `cost_metrics`) and optional cloud sync persist operational metadata only:
   - Run identifier, timestamp, integration (`vscode`, `browser`, `mcp`, `gateway`), provider/model ID
   - Content type, optimization mode, transformation method names, validation status, diagnostic score `Q`, latency `duration_ms`
   - Token counts (`original`, `optimized`, `saved`, `reduction_percentage`), accuracy label (`exact` | `estimated`), and cost estimate metadata
3. **Explicit local history control:** Retaining raw before/after prompt text locally for a user-facing history UI is opt-in (`store_raw_history_locally = false` by default), strictly local, and paired with configurable retention days and instant user purge controls.

---

## 2. Cryptographic Hashing & Low-Entropy Data Rule

> **Mandatory Rule (Section 17):** *Hashes should not be treated as anonymization guarantees for low-entropy content.*

- Short prompts, common instructions, or single-line error messages have low entropy and are trivially vulnerable to dictionary reversal even under SHA-256.
- Therefore:
  - Content hashes (`block_hash`, `file_hash`, `workspace_key_hash`) are **local lookup keys only**.
  - Raw or unsalted content hashes must **not** be uploaded to cloud analytics as "anonymized" user metrics.

---

## 3. Logging & Secret Redaction Rules

1. **No request-body logging:** Production and local-runtime logs must not dump incoming HTTP request bodies (`content`, `items`, `output`) or upstream provider responses.
2. **Automatic secret scrubbing:** Before writing error traces or diagnostic logs, strip and mask:
   - `Authorization` / `x-api-key` headers
   - Common API key prefixes and bearer tokens
   - Database URLs / credential pairs
3. **Sanitized validation errors:** Schema validation failures (`422`) return field paths and constraint descriptions without echoing rejected input string fragments.

---

## 4. Telemetry & User Retention Controls

- **Opt-in telemetry only:** No background telemetry beacons are enabled on installation. If the user opts in, documentation and settings UI must display the exact metadata schema transmitted.
- **Configurable retention & deletion:** Users can configure `local_retention_days` (e.g., 1–365 days), export metadata metrics, and delete all local history, `context_fingerprints`, and synced cloud analytics records on demand.
