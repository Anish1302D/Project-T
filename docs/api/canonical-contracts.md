# Canonical Contracts and Schema Generation (`packages/contracts`)

**Master Reference:** Sections 8.1, 12, and 13 of [token-optimization-platform-architecture.md](../token-optimization-platform-architecture.md).  
**Canonical Schema File:** [contracts.schema.json](./contracts.schema.json).  
**Related ADR:** [ADR-0004](../decisions/ADR-0004-canonical-api-schema-and-contract-generation.md).

---

## 1. Canonical Types

Matching Section 12, every integration and service shares these canonical definitions:

- **`OptimizationMode`:** `"safe" | "balanced" | "aggressive"`
- **`ContentType`:** `"prompt" | "developer_prompt" | "source_code" | "json" | "documentation" | "terminal_output" | "conversation" | "tool_result"`
- **`AccuracyLevel`:** `"exact" | "estimated"`

### Classifier Sub-Label Mapping
Section 7.2 shows a classifier example outputting `"type": "developer_instruction"`, whereas Section 12 defines `ContentType` as `"developer_prompt"`. To keep contracts strictly unified:
- External requests/responses always use the 8-value `ContentType` enum (`developer_prompt`).
- The internal classifier records `mapped_content_type = "developer_prompt"` while optionally preserving granular sub-labels (`developer_instruction`, `bug_report`, etc.) inside analysis metadata.

---

## 2. Wire Format (`snake_case`) vs. TypeScript Client Interfaces (`camelCase`)

Section 12 defines both the HTTP JSON wire format (`snake_case`, nested `tokens`/`validation`/`optimization` objects) and ergonomic TypeScript SDK contracts (`camelCase`, flat summary fields). `packages/contracts` reconciles both cleanly:

| Wire JSON (`OptimizationRequestWire` / `OptimizationResultWire`) | TypeScript SDK (`OptimizationRequest` / `OptimizationResult`) | Notes |
|---|---|---|
| `content` | `content` | Required input string |
| `content_type` | `contentType` | `ContentType` enum |
| `provider` | `provider?` | Optional target provider |
| `model` | `model?` | Optional target model |
| `mode` | `mode` | `OptimizationMode` |
| `optimization.preserve_identifiers` | `preserveIdentifiers` | Defaults `true` |
| `request_id` | `requestId` | Unique trace ID |
| `original_content` | `originalContent` | Guaranteed recoverable original |
| `optimized_content` | `optimizedContent` | Candidate or fallback original |
| `tokens.original` | `originalTokens` | Baseline count |
| `tokens.optimized` | `optimizedTokens` | Post-optimization count |
| `tokens.saved` | `tokensSaved` | `original - optimized` |
| `tokens.reduction_percentage` | `reductionPercentage` | `((original - optimized) / original) * 100` |
| `tokens.accuracy` | `accuracy` | `"exact" \| "estimated"` |
| `validation.passed` | `validationPassed` | Hard invariant pass flag |
| `optimization.methods` | `methods` | Ordered transformation IDs |
| `warnings` | `warnings` | Diagnostics / fallback reasons |
| `duration_ms` | `durationMs` | Total pipeline latency |

### Reference TypeScript Interfaces
```typescript
export type OptimizationMode = "safe" | "balanced" | "aggressive";

export type ContentType =
  | "prompt"
  | "developer_prompt"
  | "source_code"
  | "json"
  | "documentation"
  | "terminal_output"
  | "conversation"
  | "tool_result";

export interface OptimizationRequest {
  content: string;
  contentType: ContentType;
  provider?: string;
  model?: string;
  mode: OptimizationMode;
  preserveIdentifiers: boolean;
}

export interface OptimizationResult {
  requestId: string;
  originalContent: string;
  optimizedContent: string;
  originalTokens: number;
  optimizedTokens: number;
  tokensSaved: number;
  reductionPercentage: number;
  validationPassed: boolean;
  accuracy: "exact" | "estimated";
  methods: string[];
  warnings: string[];
  durationMs: number;
}
```

---

## 3. Versioning & Validation Workflow

1. **Source of Truth:** `packages/contracts/schemas/` (seeded from [contracts.schema.json](./contracts.schema.json) and [openapi-local-v1.yaml](./openapi-local-v1.yaml)).
2. **Code Generation & CI Drift Guard:**
   - Generate or validate Python Pydantic v2 models and TypeScript wire types from the JSON Schema / OpenAPI specs.
   - CI executes a verification script checking that FastAPI's runtime `/openapi.json` schema and TypeScript `packages/contracts/types/` match the canonical schemas with zero unreviewed diff.
3. **Breaking Change Policy:**
   - Additive optional response fields are backward-compatible within `/api/v1`.
   - Removing fields, narrowing enums, or changing required request fields requires bumping the major contract version (`/api/v2`) and an architecture review.
