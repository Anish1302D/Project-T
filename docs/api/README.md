# API and Contract Specifications

This directory specifies all local HTTP APIs, canonical cross-language contracts, MCP tool definitions, and API Gateway proxy interfaces for Project T.

## Index

| Document | Scope |
|---|---|
| [Local Runtime HTTP API](./local-runtime-api.md) | Developer guide, auth rules, rate/size limits, and behavior for `http://127.0.0.1:4765/api/v1` |
| [Local Runtime OpenAPI 3.1 Spec](./openapi-local-v1.yaml) | Machine-readable OpenAPI 3.1 definition covering all 10 initial local endpoints |
| [Canonical Contracts Guide](./canonical-contracts.md) | Schema versioning, wire `snake_case` vs. TS `camelCase` mapping, and Pydantic/TS codegen workflow |
| [Canonical JSON Schema](./contracts.schema.json) | Draft 2020-12 JSON Schema definitions for core types (`OptimizationRequest`, `OptimizationResult`, `TokenCountResult`, etc.) |
| [MCP Server Tools Specification](./mcp-tools-specification.md) | Typed schemas, input limits, untrusted-data guardrails, and local-vs-cloud labels for all 7 MCP tools |
| [API Gateway Specification](./api-gateway-specification.md) | Provider normalization, streaming SSE, retry/idempotency, usage reconciliation, bypass mode, and schema invariance |
