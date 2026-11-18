# ADR-0004: Canonical API Schema and Contract Generation

- **Status:** Proposed
- **Date:** 2026-11-18
- **Review Date:** 2027-01-15
- **Owners:** Project T Architecture
- **Related Master Doc Sections:** Sections 4, 8, 12, 13, 18

---

## Context

Project T operates across two primary type systems:

- **Python (`Pydantic` v2):** Core optimization engine, Local Runtime (`FastAPI`), and API Gateway.
- **TypeScript:** Browser extension, VS Code extension, MCP server, Cloud Dashboard, and `packages/contracts`.

Section 12 of the Master Architecture requires that:
- Contracts are versioned and validated at runtime.
- Python and TypeScript representations are generated from or verified against a canonical schema where practical.

Additionally, Section 12 exhibits a subtle representation difference between the HTTP JSON payload examples (nested `snake_case`, e.g., `request_id`, `tokens.original`, `validation.passed`) and the TypeScript SDK interface sketch (flat `camelCase`, e.g., `requestId`, `originalTokens`, `validationPassed`). Without a single canonical schema and explicit serialization convention, Python and TypeScript implementations will drift.

## Decision

1. **Canonical Source of Truth in `packages/contracts/schemas/`:**
   - Maintain versioned **JSON Schema (Draft 2020-12)** definitions and **OpenAPI 3.1** specifications (seeded from [contracts.schema.json](../api/contracts.schema.json) and [openapi-local-v1.yaml](../api/openapi-local-v1.yaml)) as the canonical contract source.
2. **Wire Format Standardization:**
   - All HTTP JSON wire payloads (`/api/v1/*`) use **`snake_case`** matching the structured Section 12 HTTP examples (`request_id`, `original_content`, `tokens`, `validation`, `optimization`, `duration_ms`, `warnings`).
   - TypeScript client adapters in `packages/contracts` provide idiomatic **`camelCase` TypeScript types** plus validated transport mappers (converting wire `snake_case` <-> client `camelCase`, or exposing typed DTOs directly) and runtime schema validation (e.g., Zod or AJV) at extension/gateway boundaries.
3. **Contract Versioning & Generation Workflow:**
   - Prefix HTTP endpoints with `/api/v1` and include a `schema_version` / contract compatibility metadata header or field for breaking-change tracking.
   - Generate or validate Python Pydantic models (`datamodel-code-generator` or CI schema export diff) and TypeScript types (`json-schema-to-typescript` / `openapi-typescript`) in CI so any drift fails the build.
4. **Canonical Enum Alignment:**
   - Standardize `ContentType` as the 8-value enum (`prompt`, `developer_prompt`, `source_code`, `json`, `documentation`, `terminal_output`, `conversation`, `tool_result`), mapping internal classifier sub-labels (such as `developer_instruction`) cleanly onto `developer_prompt` + sub-classification metadata.

## Alternatives Considered

### Option A: Pydantic-first (Python models generate OpenAPI -> TypeScript)
- **Pros:** Native FastAPI OpenAPI generation; zero manual JSON Schema editing.
- **Cons:** Couples the canonical contract definition to Python source code and runtime imports, making contract-first cross-team review slightly harder before `local-runtime` exists.
- **Why rejected / modified:** While FastAPI exports OpenAPI cleanly, keeping JSON Schema + OpenAPI specs in `packages/contracts/schemas/` ensures Week 1 Foundation delivers language-neutral contracts before Python runtime code is written. In CI, FastAPI's generated OpenAPI schema can be diffed against the canonical spec.

### Option B: Protocol Buffers / gRPC
- **Pros:** Compact binary wire format and strict codegen.
- **Cons:** Poor ergonomics for Chrome Manifest V3 browser extensions, standard REST debugging, and JSON-native MCP/provider payloads.
- **Why rejected:** HTTP+JSON / OpenAPI is mandated by Sections 10 and 12.

### Option C: Hand-maintained separate Python Pydantic and TypeScript `.d.ts` files
- **Pros:** No codegen tooling needed initially.
- **Cons:** High risk of silent field drift, enum mismatches, and broken client deserialization.
- **Why rejected:** Explicitly discouraged by Section 12 ("generated from or checked against a canonical schema").

## Consequences

### Positive
- Eliminates Python vs TypeScript schema drift across 6 apps.
- Resolves the HTTP `snake_case` nested vs TS `camelCase` flat discrepancy cleanly via explicit adapter mapping in `packages/contracts`.
- Enables mock server generation, contract tests, and OpenAPI docs automatically.

### Negative / Trade-offs
- Requires maintaining a CI contract verification script (`scripts/`) that validates JSON Schema -> TS/Pydantic synchronization.

### Risks & Mitigations
- **Risk:** Generated types become overly verbose or unergonomic for React/VS Code UIs.
  - **Mitigation:** Keep generated wire types distinct from ergonomic UI view-models in `packages/contracts/types/` with explicit pure mapper functions covered by unit tests.

## Review Triggers

- Review on **2027-01-15** (during Week 1–4 implementation) once FastAPI's live `/openapi.json` output is tested against `json-schema-to-typescript` / `openapi-typescript` tooling.
