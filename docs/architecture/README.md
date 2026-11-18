# Architecture Specifications

This directory expands the [Master Technical Architecture](../token-optimization-platform-architecture.md) into detailed subsystem specifications, boundary definitions, data schemas, and engineering standards.

## Index

| Document | Scope |
|---|---|
| [System Overview](./system-overview.md) | Layered architecture, component responsibilities, core principles, and module dependency rules |
| [Local Runtime & Cloud Control Plane](./local-runtime-and-cloud-control-plane.md) | `127.0.0.1:4765` runtime daemon, offline capabilities, lifecycle, and optional cloud sync |
| [Optimization Engine](./optimization-engine.md) | 10 core modules, hybrid pipeline orchestration, optimization modes, and rollback guarantees |
| [Provider & Tokenizer Adapters](./provider-and-tokenizer-adapters.md) | `TokenizerAdapter`, `TokenCountResult`, provider registry, and versioned pricing separation |
| [Integration Architecture](./integration-architecture.md) | Browser extension (MV3), VS Code extension, MCP server, API Gateway, and Cloud Dashboard |
| [Database Architecture](./database-architecture.md) | SQLite local persistence, PostgreSQL cloud schema, 12 core entities, data minimization, and FTS |
| [Reference SQL Schema](./schema.sql) | Portable SQL reference DDL for the 12 core entities (SQLite & PostgreSQL notes) |
| [Repository & Engineering Standards](./repository-and-engineering-standards.md) | Monorepo layout (`project-t`), tech stack, branch workflow, release milestones, and CI gates |
| [Roadmap, MVP Scope & Limitations](./roadmap-mvp-and-limitations.md) | MVP v0.1–v0.5 & v1.0, out-of-scope items, 10-week plan, Milestone 1 DoD, and current limitations |
| [Phased Implementation Plan](../implementation-plan.md) | Executable Phase 0–10 engineering tasks, branches, release tags, and verification gates |
