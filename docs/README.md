# Project T Documentation

Documentation suite for **Project T** (working name) — a model-independent, local-first, quality-aware token optimization platform.

> **Status:** Pre-implementation specification (Week 1 Foundation). The master architecture is defined in [Master Technical Architecture](./token-optimization-platform-architecture.md), and this `docs/` directory decomposes it into actionable specifications, contracts, schemas, security models, benchmark standards, and Architecture Decision Records (ADRs).

---

## Documentation Map

| Area | Path | Purpose |
|---|---|---|
| **Master Architecture** | [token-optimization-platform-architecture.md](./token-optimization-platform-architecture.md) | Canonical top-level product scope, principles, stack, and 10-week plan |
| **Implementation Plan** | [implementation-plan.md](./implementation-plan.md) | Actionable Phase 0–10 engineering execution plan, deliverables, and exit gates |
| **Architecture Specs** | [architecture/](./architecture/README.md) | Layered system overview, runtime/cloud split, engine internals, adapters, integrations, database ERD/DDL, repo & roadmap |
| **API & Contracts** | [api/](./api/README.md) | Local Runtime REST API (`127.0.0.1:4765/api/v1`), OpenAPI 3.1 spec, canonical JSON Schema, MCP tools, API Gateway spec |
| **Algorithms** | [algorithms/](./algorithms/README.md) | Hybrid pipeline, modes, classification, constraints/protected spans, deduplication, compression, BM25, token & quality math |
| **Security & Privacy** | [security/](./security/README.md) | Localhost security, credential boundaries, 9-threat model, data minimization, redaction, and opt-in telemetry rules |
| **Benchmarks & QA** | [benchmarks/](./benchmarks/README.md) | 8 benchmark categories, paired evaluation protocol, token/cost accounting distinctions, and release acceptance targets |
| **Architecture Decisions** | [decisions/](./decisions/README.md) | ADR template and ADRs 0001–0012 covering foundational architecture choices |

---

## Recommended Reading Order

### For First-Time Contributors & Architects
1. [Master Technical Architecture](./token-optimization-platform-architecture.md)
2. [System Overview](./architecture/system-overview.md) and [Roadmap, MVP Scope & Known Limitations](./architecture/roadmap-mvp-and-limitations.md)
3. [Architecture Decision Records Index](./decisions/README.md)
4. [Repository & Engineering Standards](./architecture/repository-and-engineering-standards.md)

### For Milestone 1 (Core Engine v0.1 & Local Runtime)
1. [Optimization Engine Architecture](./architecture/optimization-engine.md)
2. [Algorithm Specifications](./algorithms/README.md)
3. [Canonical Contracts](./api/canonical-contracts.md) and [Local Runtime API](./api/local-runtime-api.md)
4. [Database Architecture](./architecture/database-architecture.md) and [Reference SQL Schema](./architecture/schema.sql)
5. [Security Architecture](./security/security-architecture.md) and [Benchmark Acceptance Criteria](./benchmarks/acceptance-criteria.md)

### For Integration Developers (VS Code, Browser, MCP, Gateway)
1. [Integration Architecture](./architecture/integration-architecture.md)
2. [Provider & Tokenizer Adapters](./architecture/provider-and-tokenizer-adapters.md)
3. [MCP Tools Specification](./api/mcp-tools-specification.md) or [API Gateway Specification](./api/api-gateway-specification.md)
4. [Threat Model](./security/threat-model.md) and [Privacy & Data Handling](./security/privacy-and-data-handling.md)

---

## Traceability to Master Architecture

Every section of [token-optimization-platform-architecture.md](./token-optimization-platform-architecture.md) maps directly to detailed specifications in this directory:

- **Sections 1–4, 10, 13–15, 18, 20–23** -> [architecture/](./architecture/README.md)
- **Sections 5, 11** -> [local-runtime-and-cloud-control-plane.md](./architecture/local-runtime-and-cloud-control-plane.md) & [database-architecture.md](./architecture/database-architecture.md)
- **Sections 6–7, 21** -> [algorithms/](./algorithms/README.md)
- **Sections 8–9, 12** -> [provider-and-tokenizer-adapters.md](./architecture/provider-and-tokenizer-adapters.md), [integration-architecture.md](./architecture/integration-architecture.md), & [api/](./api/README.md)
- **Section 16** -> [benchmarks/](./benchmarks/README.md)
- **Section 17** -> [security/](./security/README.md)
- **Section 19** -> [decisions/](./decisions/README.md)
