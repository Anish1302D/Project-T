# Contributing to Project T

Thank you for contributing to **Project T**. Please follow the architectural boundaries and engineering workflow established in [Repository & Engineering Standards](./docs/architecture/repository-and-engineering-standards.md).

## Branching & Pull Requests

1. Never commit directly to `main`.
2. Branch off `develop` using prefixes:
   - `feature/<scope>` (e.g., `feature/optimization-core`, `feature/local-runtime`)
   - `fix/<scope>`
   - `test/<scope>`
   - `docs/<scope>`
3. Keep pull requests focused, small, and reviewable.
4. Any breaking pipeline or contract change requires an ADR review in `docs/decisions/`.

## Required Pre-Merge Checks

Run locally before opening a PR:

```bash
corepack pnpm run lint
corepack pnpm run typecheck
corepack pnpm run build
corepack pnpm run test
python scripts/verify_contracts.py
pytest
```

## Architecture Guardrails

- **Local-first & Privacy by default:** Never introduce implicit cloud uploads or raw prompt/code logging.
- **Engine independence:** `packages/optimization-core` must not depend on `apps/*`, `services/*`, FastAPI, browser APIs, VS Code APIs, or vendor provider SDKs.
- **Contract parity:** Keep `docs/api/` schemas, `packages/contracts/schemas/`, Python Pydantic models, and TypeScript interfaces synchronized.
