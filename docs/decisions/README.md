# Architecture Decision Records (ADRs)

This directory contains the foundational Architecture Decision Records required prior to implementation (per Section 19 of the [Master Technical Architecture](../token-optimization-platform-architecture.md#19-architecture-decision-records-to-create)).

Every ADR documents **Context**, **Decision**, **Alternatives Considered**, **Consequences**, and a **Review Date** using [ADR-TEMPLATE.md](./ADR-TEMPLATE.md).

---

## Decision Register

| ID | Title | Status | Review Date | Link |
|---|---|---|---|---|
| ADR-0001 | Monorepo and Workspace Tooling | Accepted | 2027-02-18 | [ADR-0001](./ADR-0001-monorepo-and-workspace-tooling.md) |
| ADR-0002 | Python Optimization Engine and TypeScript Integration Layer | Accepted | 2027-02-18 | [ADR-0002](./ADR-0002-python-engine-and-typescript-integrations.md) |
| ADR-0003 | Local Runtime Transport and Authentication | Accepted | 2027-02-18 | [ADR-0003](./ADR-0003-local-runtime-transport-and-auth.md) |
| ADR-0004 | Canonical API Schema and Contract Generation | Accepted | 2027-02-18 | [ADR-0004](./ADR-0004-canonical-api-schema-and-contract-generation.md) |
| ADR-0005 | Tokenizer Adapter Interface and Exact/Estimated Labeling | Accepted | 2027-02-18 | [ADR-0005](./ADR-0005-tokenizer-adapter-and-accuracy-labeling.md) |
| ADR-0006 | Optimization Pipeline Ordering and Fallback Policy | Accepted | 2027-02-18 | [ADR-0006](./ADR-0006-pipeline-ordering-and-fallback-policy.md) |
| ADR-0007 | Protected-Span and Constraint-Preservation Strategy | Accepted | 2027-02-18 | [ADR-0007](./ADR-0007-protected-spans-and-constraint-preservation.md) |
| ADR-0008 | Local SQLite Schema and Cloud PostgreSQL Sync Boundaries | Proposed | 2027-03-01 | [ADR-0008](./ADR-0008-sqlite-local-and-postgresql-cloud-sync-boundaries.md) |
| ADR-0009 | MCP Tool Naming and Contracts | Accepted | 2027-02-18 | [ADR-0009](./ADR-0009-mcp-tool-naming-and-contracts.md) |
| ADR-0010 | Browser Permissions and Supported Website Adapter Strategy | Proposed | 2027-03-01 | [ADR-0010](./ADR-0010-browser-permissions-and-site-adapters.md) |
| ADR-0011 | Privacy, Telemetry, Retention, and Content Storage | Accepted | 2027-02-18 | [ADR-0011](./ADR-0011-privacy-telemetry-retention-and-storage.md) |
| ADR-0012 | Benchmark Methodology and Release Acceptance Criteria | Proposed | 2027-02-18 | [ADR-0012](./ADR-0012-benchmark-methodology-and-release-criteria.md) |

---

## Status Definitions

- **Accepted:** Locked for v0.1 foundation and architecture; changing requires a superseding ADR and architecture review.
- **Proposed:** Aligned with Master Technical Architecture v1.0, pending specific implementation-time validation (e.g., codegen CLI choice, exact benchmark fixture baselines, or target browser DOM selector stability).
- **Superseded:** Replaced by a newer ADR (linked in header).

## Creating a New ADR

1. Copy [ADR-TEMPLATE.md](./ADR-TEMPLATE.md) to `ADR-NNNN-short-kebab-title.md`.
2. Fill in every required section: Context, Decision, Alternatives Considered, Consequences, and Review Date.
3. Add the ADR to the register table above via pull request on a `docs/*` branch.
