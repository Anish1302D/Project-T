# Project T (Working Name)

Model-independent, local-first, quality-aware token optimization platform across prompts, workspace context, terminal logs, MCP tools, browser extensions, and API gateways.

> **Release `v1.0.0`:** All MVP components implemented and verified across Python, TypeScript, and Playwright E2E suites. See [Implementation Plan](./docs/implementation-plan.md) and [Roadmap & Limitations](./docs/architecture/roadmap-mvp-and-limitations.md).

---

## Repository Layout

- `docs/` — [Master Architecture](./docs/token-optimization-platform-architecture.md), detailed specs, OpenAPI/JSON schemas, SQLite/PostgreSQL DDL, and accepted ADRs 0001–0012
- `packages/` — Core libraries (`contracts`, `optimization-core`, `provider-adapters`, `shared-utils`, `shared-ui`)
- `apps/` — Runtimes and integrations (`local-runtime`, `vscode-extension`, `mcp-server`, `browser-extension`, `api-gateway`, `dashboard`)
- `services/` — Optional cloud control plane (`authentication`, `cloud_sync`, `analytics`)
- `benchmarks/` — Reproducible 8-category & paired evaluation runners, datasets, and reports
- `infrastructure/` — SQLite/PostgreSQL migrations and Docker packaging (`docker-compose.yml`)
- `scripts/` — Contract parity verification (`verify_contracts.py`) and release packager (`package_release.py`)
- `tests/` — Cross-cutting unit, integration, security (threat-model & sync boundaries), E2E, and regression suites

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
