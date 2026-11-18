# Repository Structure and Engineering Standards

**Master Reference:** Sections 10, 13, 18, and 20 of [token-optimization-platform-architecture.md](../token-optimization-platform-architecture.md).  
**Related ADR:** [ADR-0001](../decisions/ADR-0001-monorepo-and-workspace-tooling.md), [ADR-0002](../decisions/ADR-0002-python-engine-and-typescript-integrations.md).

---

## 1. Monorepo Directory Blueprint (`project-t`)

Matching Section 13:

```text
project-t/
├── apps/
│   ├── dashboard/           # React + Vite + Tailwind cloud/local analytics UI
│   │   └── src/{components,pages,charts,hooks,services}/
│   ├── browser-extension/   # TypeScript + React + Chrome Manifest V3
│   │   └── src/{background,content,popup,options,integrations}/
│   ├── vscode-extension/    # TypeScript + VS Code Extension API
│   │   └── src/{commands,providers,views,context,terminal,runtime}/
│   ├── local-runtime/       # Python 3.12+ FastAPI local HTTP runtime (127.0.0.1:4765)
│   │   └── src/{server,auth,config,lifecycle}/
│   ├── api-gateway/         # Python 3.12+ FastAPI proxy & usage reconciliation
│   │   └── src/{routes,middleware,providers,streaming,usage}/
│   └── mcp-server/          # TypeScript Official MCP SDK server
│       └── src/{tools,resources,server.ts}
├── packages/
│   ├── contracts/           # Canonical JSON Schemas, OpenAPI specs, generated TS/Pydantic types
│   │   ├── schemas/
│   │   └── types/
│   ├── optimization-core/   # Engine core (zero UI/IDE/browser/SDK dependencies)
│   │   ├── classifier/
│   │   ├── constraints/
│   │   ├── deduplication/
│   │   ├── compression/
│   │   ├── context-selection/
│   │   ├── validation/
│   │   ├── tokenization/
│   │   └── pipeline/
│   ├── provider-adapters/   # TokenizerAdapter, request serializers, versioned model/pricing registry
│   │   ├── openai/
│   │   ├── anthropic/
│   │   ├── google/
│   │   └── registry/
│   ├── shared-ui/           # Shared React + Tailwind components
│   └── shared-utils/        # Shared TS utility helpers
├── services/                # Optional cloud control-plane services (MVP v0.5)
│   ├── analytics/
│   ├── authentication/
│   └── cloud-sync/
├── benchmarks/              # Reproducible benchmark datasets, evaluators, reports, runner
│   ├── datasets/
│   ├── evaluation/
│   ├── reports/
│   └── runner/
├── tests/                   # Cross-cutting test suites
│   ├── unit/
│   ├── integration/
│   ├── e2e/
│   ├── security/
│   └── regression/
├── infrastructure/
│   ├── docker/
│   ├── database/
│   ├── deployment/
│   └── monitoring/
├── docs/                    # Architecture, API, algorithms, security, benchmarks, ADRs
├── scripts/                 # Contract verification, lint, benchmark helpers
├── .github/workflows/       # CI pipelines
├── docker-compose.yml
├── pnpm-workspace.yaml
├── turbo.json
├── pyproject.toml
├── README.md
├── CONTRIBUTING.md
└── LICENSE
```

---

## 2. Technology Stack Summary

| Layer | Technology | Purpose |
|---|---|---|
| Monorepo | `pnpm` + `Turborepo` | JS/TS workspace & build/test caching |
| Core Engine & APIs | Python 3.12+, `FastAPI`, `Pydantic` | Optimization core, Local Runtime, API Gateway |
| Lexical Search & Similarity | `BM25` / SQLite `FTS5`, `SimHash` / `MinHash` | Workspace relevance & near-duplicate candidates |
| Frontend & Extensions | `TypeScript`, `React`, `Vite`, `Tailwind CSS` | Dashboard, Chrome Manifest V3, VS Code Extension |
| Agent Protocol | Official `MCP SDK` | Typed agent tool interoperability |
| Persistence | `SQLite` (local), `PostgreSQL` (cloud), `Redis` (cloud cache) | Offline-first storage & optional cloud sync (`pgvector` deferred to P2) |
| Testing | `Pytest`, `Vitest`, `Playwright` | Python, TypeScript, and browser/dashboard E2E |
| Automation & Packaging | `GitHub Actions`, `Docker` | CI checks and reproducible cloud packaging |

**Explicitly excluded in v1:** Kubernetes, mandatory vector databases, and distributed microservices.

---

## 3. Repository Boundary Enforcement

1. `packages/optimization-core` must **never** import from `apps/*`, `services/*`, browser APIs, VS Code APIs, or vendor provider SDKs.
2. All cross-language communication passes through `packages/contracts`.
3. Provider-specific tokenization, serialization, and pricing metadata live strictly inside `packages/provider-adapters`.
4. `apps/local-runtime` must boot and pass optimization requests with zero network or cloud access.
5. Browser extension bundles and frontend packages must never contain provider API keys or server secrets.
6. Every optimization algorithm must ship with dedicated unit tests and benchmark fixtures.
7. Pipeline-breaking or boundary-changing PRs require an ADR update and architecture review.

---

## 4. Git Workflow & Branching Standards

### Branch Naming
```text
main                       # Protected release branch; never commit/develop directly
develop                    # Integration branch for verified feature PRs

feature/optimization-core
feature/local-runtime
feature/vscode-extension
feature/mcp-server
feature/browser-extension
feature/api-gateway
feature/cloud-dashboard

fix/*                      # Bug fixes
test/*                     # Test & benchmark additions
docs/*                     # Documentation & ADR updates
```

### Pull Request & Release Rules
- Never develop directly on `main`.
- All changes enter via focused, reviewable pull requests on `feature/*`, `fix/*`, `test/*`, or `docs/*`.
- CI must pass unit tests, integration/regression checks, contract sync verification, and linters before merge.
- Tag releases using Semantic Versioning (`MAJOR.MINOR.PATCH`).

### Target Release Milestones
```text
v0.1.0  Core Engine
v0.2.0  Local Runtime
v0.3.0  IDE Integration
v0.4.0  Browser Integration
v0.5.0  MCP and Gateway
v1.0.0  Universal Platform MVP
```
