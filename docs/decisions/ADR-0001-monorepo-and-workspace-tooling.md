# ADR-0001: Monorepo and Workspace Tooling

- **Status:** Accepted
- **Date:** 2026-11-18
- **Review Date:** 2027-02-18
- **Owners:** Project T Architecture
- **Related Master Doc Sections:** Sections 4, 10, 13, 18

---

## Context

Project T spans multiple runtime environments and client integrations:

- A Python 3.12+ optimization core (`packages/optimization-core`), local FastAPI runtime (`apps/local-runtime`), and API gateway (`apps/api-gateway`).
- TypeScript/React applications and extensions: VS Code extension (`apps/vscode-extension`), Chrome Manifest V3 browser extension (`apps/browser-extension`), MCP server (`apps/mcp-server`), and cloud dashboard (`apps/dashboard`), plus shared UI/utility/contract packages (`packages/contracts`, `packages/provider-adapters`, `packages/shared-ui`, `packages/shared-utils`).
- Shared benchmark suites (`benchmarks/`), multi-layer test suites (`tests/`), and infrastructure definitions (`infrastructure/`).

Keeping integrations synchronized with shared schemas and avoiding premature distributed-service overhead requires coordinated builds, atomic cross-package changes, and clear module boundaries without microservices complexity.

## Decision

Adopt a **modular monorepo** (`project-t`) managed by:

1. **JavaScript/TypeScript workspaces:** `pnpm` (`pnpm-workspace.yaml`) + `Turborepo` (`turbo.json`) for task orchestration, build caching, and dependency-aware workspace execution across `apps/*` and `packages/*`.
2. **Python workspace management:** Root `pyproject.toml` coordinating Python 3.12+ packages (`packages/optimization-core`, `apps/local-runtime`, `apps/api-gateway`) with `pytest` for unit, integration, and regression tests.
3. **Strict module boundary enforcement:** `optimization-core` must remain zero-dependency with respect to browser, IDE, dashboard, gateway, and cloud infrastructure code.
4. **No microservices or Kubernetes in v1:** Deploy and test as cohesive modular applications (`local-runtime`, `api-gateway`, optional cloud control services) before considering process splitting.

## Alternatives Considered

### Option A: Separate repositories per component (Polyrepo)
- **Pros:** Independent repo permissions and simple per-repo CI triggers.
- **Cons:** High friction synchronizing shared contracts (`packages/contracts`) between Python engine and TypeScript clients; version skew across extensions and local runtime; fragmented benchmark/E2E testing.
- **Why rejected:** Tight contract alignment during rapid v0.1–v1.0 iteration makes polyrepo synchronization an unnecessary bottleneck.

### Option B: Nx or Bazel monorepo
- **Pros:** Strong polyglot task graph support (especially Bazel).
- **Cons:** Steep operational/configuration overhead for a small-to-medium initial engineering footprint; heavy Bazel rule maintenance on Windows/macOS/Linux developer machines.
- **Why rejected:** Violates the simplicity principle for Week 1 Foundation; `pnpm + Turborepo` paired with `pyproject.toml` covers JS/TS and Python cleanly with minimal setup.

### Option C: Microservices architecture from day one
- **Pros:** Independent scaling per service.
- **Cons:** Premature network serialization, service discovery, and deployment overhead (e.g., Kubernetes) before the optimization engine proves value.
- **Why rejected:** Explicitly out of scope per Sections 4 and 10 of the Master Architecture.

## Consequences

### Positive
- Atomic pull requests can update a contract schema, Python backend handler, TypeScript client, and regression test together.
- Turborepo caches TS builds/tests (`vitest`, `tsc`, lint) across apps and packages.
- Clear top-level directory separation (`apps/`, `packages/`, `services/`, `benchmarks/`, `tests/`, `infrastructure/`, `docs/`) enforces architectural layering.

### Negative / Trade-offs
- Polyglot monorepo requires contributors working across boundaries to have both Node/pnpm and Python 3.12+ toolchains installed.
- CI workflows (`.github/workflows/`) must orchestrate both JS/TS (`pnpm`/`turbo`) and Python (`pytest`) pipelines, with path filtering to keep PR checks fast.

### Risks & Mitigations
- **Risk:** Accidental cross-layer imports (e.g., `optimization-core` importing FastAPI or provider SDKs).
  - **Mitigation:** Enforce package import rules in Python packaging (`pyproject.toml` dependencies) and CI boundary lint checks.

## Review Triggers

- Review on **2027-02-18** (post-v0.4 milestone) or earlier if polyglot task orchestration between Turborepo and Python builds creates measurable CI slowdowns.
