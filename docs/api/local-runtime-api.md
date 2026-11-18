# Local Runtime HTTP API (`/api/v1`)

**Master Reference:** Sections 5, 12, and 20 of [token-optimization-platform-architecture.md](../token-optimization-platform-architecture.md).  
**Machine-Readable Spec:** [openapi-local-v1.yaml](./openapi-local-v1.yaml).  
**Related ADR:** [ADR-0003](../decisions/ADR-0003-local-runtime-transport-and-auth.md), [ADR-0004](../decisions/ADR-0004-canonical-api-schema-and-contract-generation.md).

---

## 1. Base URL, Transport & Authentication

- **Base URL:** `http://127.0.0.1:4765/api/v1`
- **Bind Constraint:** Binds strictly to loopback `127.0.0.1` by default (never `0.0.0.0`).
- **Authentication:** `Authorization: Bearer <installation_token>` required on every endpoint except `GET /health` (which returns status/version metadata only).
- **Origin & CORS Guards:**
  - `Origin` header checked against explicit configured extension/local client allowlist (no wildcard `*`).
  - `Host` header restricted to `127.0.0.1:4765` / `localhost:4765` to block DNS rebinding.
- **Safety Limits:**
  - Maximum payload size enforced (configurable default, e.g., 2 MB per request; 413 Payload Too Large on overflow).
  - Per-request execution timeout enforced with automatic fallback/error handling.
  - Sliding-window local rate limiting (`429 Too Many Requests`).

---

## 2. Endpoint Summary

| Endpoint | Method | Auth | Purpose |
|---|---|---|---|
| `/health` | `GET` | Optional | Runtime liveness, engine version, SQLite readiness (no secrets/user data) |
| `/optimize` | `POST` | Required | Classify, compress, validate, count tokens, and return reversible result |
| `/count` | `POST` | Required | Count or estimate tokens for plain text or structured request |
| `/analyze` | `POST` | Required | Classify content, extract constraints, list protected spans without mutating |
| `/context/select` | `POST` | Required | Rank task-relevant files/snippets from an approved workspace using BM25/FTS |
| `/context/compress` | `POST` | Required | Compress multi-snippet context packs or conversation history with provenance |
| `/logs/compress` | `POST` | Required | Extract errors, stack frames, file/line refs, and test summaries from terminal logs |
| `/metrics` | `GET` | Required | Aggregated metadata-only usage, token savings, accuracy, and fallback metrics |
| `/settings` | `GET` / `PUT` | Required | Read or update local optimization rules, retention, and cloud sync opt-in flags |
| `/providers` | `GET` | Required | List configured providers, models, tokenizer support, and pricing version info |

---

## 3. Core Optimization Endpoint (`POST /optimize`)

### Example Request
```json
{
  "content": "Original content here",
  "content_type": "developer_prompt",
  "provider": "openai",
  "model": "example-model",
  "mode": "balanced",
  "optimization": {
    "deduplicate": true,
    "semantic_compression": false,
    "context_filtering": true,
    "preserve_identifiers": true
  }
}
```

### Example Response (Illustrative Only)
```json
{
  "request_id": "req_example",
  "original_content": "Original content here",
  "optimized_content": "Optimized content here",
  "tokens": {
    "original": 1200,
    "optimized": 820,
    "saved": 380,
    "reduction_percentage": 31.67,
    "accuracy": "estimated"
  },
  "validation": {
    "passed": true,
    "constraints_preserved": true,
    "identifiers_preserved": true
  },
  "optimization": {
    "methods": ["deduplication", "rule_based_compression"],
    "mode": "balanced"
  },
  "duration_ms": 18,
  "warnings": []
}
```
> *Note: Numerical values above are illustrative examples matching Section 12, not measured benchmark results.*

### Fail-Safe & Fallback Behavior
If `QualityValidator` rejects the candidate, if `tokens.saved <= min_meaningful_savings`, or if an internal stage errors/times out:
- HTTP status remains `200 OK` (for deterministic fallback) with:
  - `optimized_content == original_content`
  - `tokens.optimized == tokens.original`
  - `tokens.saved == 0`
  - `tokens.reduction_percentage == 0.0`
  - `validation.passed` reflects the true check outcome
  - `warnings[]` explains why fallback occurred (e.g., `"fallback_validation_failed"` or `"fallback_no_meaningful_savings"`).

---

## 4. Error Response Format

Errors never echo raw request bodies, secrets, or `Authorization` headers:

```json
{
  "error": {
    "code": "payload_too_large",
    "message": "Request body exceeds configured limit of 2097152 bytes.",
    "request_id": "req_01J..."
  }
}
```

| HTTP Status | Standard Code | Meaning |
|---|---|---|
| `400` | `invalid_request` | Malformed JSON or unsupported field values |
| `401` | `unauthorized` | Missing or invalid installation bearer token |
| `403` | `forbidden_origin` | Disallowed `Origin`/`Host` header or unapproved workspace path |
| `413` | `payload_too_large` | Input exceeds configured maximum byte size |
| `422` | `validation_error` | Schema validation failed (sanitized field paths only, no input echo) |
| `429` | `rate_limit_exceeded` | Too many local requests in configured window |
| `504` | `optimization_timeout` | Execution budget exceeded (when hard timeout abort applies) |
