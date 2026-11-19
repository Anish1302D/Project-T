# ADR-0008: Local SQLite Schema and Cloud PostgreSQL Sync Boundaries

- **Status:** Accepted
- **Date:** 2026-11-18
- **Ratified:** 2026-11-19 (Phase 9 — PostgreSQL schema & opt-in cloud sync boundary implemented and verified)
- **Review Date:** 2027-03-01
- **Owners:** Project T Architecture
- **Related Master Doc Sections:** Sections 5, 10, 11, 13, 14, 17

---

## Context

Project T is local-first (must run fully offline with local metadata and workspace index persistence) while optionally supporting a cloud control plane for cross-device settings synchronization, aggregated analytics dashboards, and team/multi-device visibility in MVP v0.5.

Using a cloud database as a prerequisite breaks offline operation and privacy defaults; conversely, letting local SQLite and cloud PostgreSQL schemas drift or accidentally syncing raw prompt text or workspace source code violates Section 11 (Data Minimization) and Section 17 (Security and Privacy).

## Decision

1. **Dual-Engine Relational Persistence:**
   - **Local database:** SQLite (with FTS5 enabled for lexical BM25/FTS context selection) embedded inside the Local Runtime, storing local settings, project profiles, context fingerprints, optimization runs, token/cost metrics, and benchmark metadata.
   - **Cloud database:** PostgreSQL (with optional `pgvector` deferred until semantic retrieval benchmarks justify it in P2), storing cloud user accounts, registered installations/devices, synced settings/rules, and aggregated usage analytics.
2. **Core Entity Alignment:**
   - Align local and cloud data models across the 12 core entities defined in Section 11 (`users`, `installations`, `devices`, `providers`, `models`, `optimization_runs`, `token_metrics`, `cost_metrics`, `project_profiles`, `context_fingerprints`, `optimization_rules`, `benchmark_results`), scoping local-only vs cloud-eligible tables explicitly (reference DDL in [schema.sql](../architecture/schema.sql)).
3. **Strict Sync Boundaries:**
   - **Default:** Cloud sync is **disabled (opt-in only)**; local optimization never depends on PostgreSQL connectivity.
   - **Eligible for opt-in sync:** User/installation registration, optimization rules/settings, provider/model metadata, and **metadata-only** optimization/token/cost metrics (counts, timestamps, mode, optimization methods, validation status, hashes/fingerprints where non-sensitive).
   - **Excluded from cloud sync by default:** Raw prompt text, optimized prompt text, workspace file contents, terminal output, and local project file paths unless scrubbed or explicitly opted into a cloud-hosted feature (e.g., optional cloud API gateway).
   - **Context fingerprints:** Strictly scoped by `(project_id, content_version/file_hash)` locally to prevent cross-project leakage and stale context reuse.
4. **Conflict Resolution & Idempotency:**
   - Analytics runs are append-only/idempotent by `(installation_id, run_id)`.
   - Settings/rules sync uses explicit monotonic version/updated_at conflict resolution with local override priority.

## Alternatives Considered

### Option A: PostgreSQL required for all modes (Docker locally)
- **Pros:** Single SQL dialect and schema everywhere.
- **Cons:** Heavy local footprint; forces desktop/IDE users to run Docker/Postgres just to optimize prompts locally.
- **Why rejected:** Violates lightweight local-first experience (Sections 5.1 & 10).

### Option B: Sync full prompt/context history to cloud for dashboard inspection
- **Pros:** Enables "view your past prompts anywhere" in cloud dashboard.
- **Cons:** Severe privacy and IP leakage risk for developer source code and proprietary prompts.
- **Why rejected:** Explicitly prohibited by Section 11 ("Data minimization") and Section 17 ("Do not upload raw prompts, source code, or terminal output to the cloud unless the user explicitly enables a feature that requires it").

## Consequences

### Positive
- Zero-dependency local persistence with SQLite + built-in FTS5 for BM25 context ranking.
- Clean separation between local sensitive project workspace data and optional cloud telemetry/settings.
- Identical domain vocabulary across local and cloud reporting.

### Negative / Trade-offs
- Requires maintaining migrations for both SQLite (local) and PostgreSQL (cloud) schemas (e.g., via SQLAlchemy/Alembic or dual migration scripts in `infrastructure/database/`).

### Risks & Mitigations
- **Risk:** Low-entropy prompt hashes synced to cloud could allow dictionary guessing of common prompts.
  - **Mitigation:** Follow Section 17 rule ("Hashes should not be treated as anonymization guarantees for low-entropy content"); omit content hashes from default cloud analytics sync unless keyed/salted locally or explicitly kept local-only.

## Review Triggers

- Reviewed and accepted in Phase 9 (**2026-11-19**):
  - Implemented PostgreSQL cloud-eligible migration ([001_initial_cloud_schema.sql](../architecture/schema.sql) -> `infrastructure/database/postgres/001_initial_cloud_schema.sql`) omitting `project_profiles`, `context_fingerprints`, `workspace_lexical_index` (`fts5`), and deferred `pgvector`.
  - Verified metadata-only boundary validator in `services/` rejecting raw prompts, code, terminal logs, filesystem paths, API secrets, and low-entropy content hashes across `POST /api/cloud/v1/sync/*`.
  - Confirmed `(installation_id, run_id)` idempotent upserts and full offline independence of `apps/local-runtime`.
- Next scheduled review: **2027-03-01**.
