# Content Classification and Constraint Extraction

**Master Reference:** Sections 7.2, 7.3, and 7.4 of [token-optimization-platform-architecture.md](../token-optimization-platform-architecture.md).  
**Related ADR:** [ADR-0007](../decisions/ADR-0007-protected-spans-and-constraint-preservation.md).

---

## 1. Content Classifier (`classifier/`)

### Purpose
Detect the structural nature of the incoming payload so downstream modules apply appropriate normalization, deduplication, and protection strategies—even when the caller omits `content_type` or mixes prose with code/logs.

### Example Input & Output (Section 7.2)
Input:
```text
Fix the authentication issue in my React application.
Check the JWT middleware and login API.
Do not change the database schema.
```

Classifier output:
```json
{
  "type": "developer_instruction",
  "mapped_content_type": "developer_prompt",
  "language": "en",
  "contains_code": false,
  "contains_constraints": true
}
```

### ContentType Mapping Rules
- Canonical API enum (`ContentType`): `prompt`, `developer_prompt`, `source_code`, `json`, `documentation`, `terminal_output`, `conversation`, `tool_result`.
- Internal granular labels (such as `developer_instruction`) map deterministically to a canonical `ContentType` (`developer_prompt`), preserving the granular subtype for adaptive rule tuning.
- Mixed payloads (e.g., prose prompt containing fenced Markdown code blocks or JSON payloads) trigger segment-level span tagging so code/JSON segments receive `safe`-mode structural protection regardless of top-level `mode`.

---

## 2. Constraint Extractor (`constraints/`)

### Purpose
Extract explicit user objectives, target components, prohibitions, and output-format requirements before any compression occurs.

### Example Structured Representation (Section 7.3)
```json
{
  "objective": "Fix authentication issue",
  "targets": ["JWT middleware", "login API"],
  "constraints": ["Do not change the database schema"]
}
```

### Constraint Signals Detected
1. **Negative prohibitions:** *"Do not..."*, *"Never..."*, *"Avoid..."*, *"Don't modify..."*, *"Without changing..."*
2. **Mandatory requirements:** *"Must..."*, *"Always..."*, *"Ensure..."*, *"Only edit..."*, *"Require..."*
3. **Scope boundaries:** Explicit file/module allowlists or exclusions.
4. **Output format contracts:** *"Return valid JSON with keys..."*, *"Respond as a unified diff"*, *"Use TypeScript strict mode"*.

---

## 3. Protected Information Categories (10 Hard Categories)

Matching Section 7.4, the extractor tags and locks spans across all ten categories prior to any transformation:

| # | Category | Examples / Detection Strategy |
|---:|---|---|
| 1 | **Function, class, and variable names** | `camelCase`, `snake_case`, `PascalCase`, backtick-quoted identifiers, AST/lexer symbols |
| 2 | **Imports and type definitions** | `import ...`, `from ... import ...`, `interface`, `type`, generics, type annotations |
| 3 | **API endpoints and HTTP methods** | `GET /api/v1/optimize`, URLs, route paths (`/users/:id`) |
| 4 | **Error codes and exact error messages** | HTTP status codes, stack exception names, quoted error strings (`ERR_CONNECTION_REFUSED`) |
| 5 | **File paths and line references** | `src/auth/jwt.ts#L42`, Windows/POSIX paths (`apps/local-runtime/src/server/app.py`) |
| 6 | **JSON keys and schema requirements** | Keys inside JSON objects/blocks, JSON Schema `$defs`/type constraints |
| 7 | **Explicit user constraints and prohibitions** | Complete clauses extracted by Constraint Extractor |
| 8 | **Tool names and tool arguments** | MCP tool names (`optimize_prompt`), function-call parameter keys and literal values |
| 9 | **Version numbers and configuration values** | SemVer (`3.12+`, `v0.1.0`), port numbers (`127.0.0.1:4765`), env keys (`PROJECT_T_PORT`), thresholds |
| 10 | **User-specified output formats** | Markdown table headers, YAML/JSON schema constraints, exact delimiter instructions |

### Span-Locking Contract
- Every protected span receives an immutable range `[start, end]` and canonical text value.
- Compressors must treat locked spans as atomic read-only tokens (via sentinel placeholders or non-overlapping edit intervals).
- `QualityValidator` verifies 100% presence and integrity of all locked spans after transformation.
