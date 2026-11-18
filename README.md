# Project T (Working Name)

Model-independent, local-first, quality-aware token optimization platform across prompts, workspace context, terminal logs, MCP tools, browser extensions, and API gateways.

> **Current Phase:** Week 1 Foundation (`packages/contracts`, monorepo tooling, and CI checks). See [Implementation Plan](./docs/implementation-plan.md).

---

## Repository Layout

- `docs/` — [Master Architecture](./docs/token-optimization-platform-architecture.md), detailed specs, OpenAPI/JSON schemas, SQLite/PostgreSQL DDL, and ADRs 0001–0012
- `packages/` — Shared libraries (`contracts`, `shared-utils`, `shared-ui`, and upcoming `optimization-core` and `provider-adapters`)
- `apps/` — Integrations and runtimes (`local-runtime`, `vscode-extension`, `mcp-server`, `browser-extension`, `api-gateway`, `dashboard`)
- `scripts/` — Contract parity verification and engineering automation
- `tests/` — Cross-cutting unit, integration, security, E2E, and regression suites

---

## Development Quickstart

### Prerequisites
- **Node.js** `>= 22` with `corepack` (`pnpm`)
- **Python** `>= 3.12` (with SQLite FTS5 enabled)

### Verify TypeScript Workspaces
```bash
corepack pnpm install
corepack pnpm run build
corepack pnpm run typecheck
corepack pnpm run test
```

### Verify Python Contracts & Schema Parity
```bash
python scripts/verify_contracts.py
pytest
```

---

## Engineering Rules

- Never develop directly on `main`; create feature/fix/docs branches from `develop`.
- Keep `packages/optimization-core` independent from UI, IDE, browser, FastAPI, and provider SDKs.
- All HTTP/API contract updates start in canonical schemas and must pass `scripts/verify_contracts.py`.
- See [CONTRIBUTING.md](./CONTRIBUTING.md) and [Repository & Engineering Standards](./docs/architecture/repository-and-engineering-standards.md).
