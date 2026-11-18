# Deduplication and Similarity Detection (`deduplication/`)

**Master Reference:** Sections 7.1, 7.6, 11, and 17 of [token-optimization-platform-architecture.md](../token-optimization-platform-architecture.md).  
**Related ADR:** [ADR-0008](../decisions/ADR-0008-sqlite-local-and-postgresql-cloud-sync-boundaries.md).

---

## 1. Staged Deduplication Strategy

Matching Section 7.6, deduplication executes in five conservative stages:

1. **Normalize safe whitespace and line endings:**
   - Standardize `\r\n` -> `\n` and strip trailing spaces on non-significant lines prior to comparison without corrupting indentation-sensitive source code (such as Python, YAML, or Markdown code fences).
2. **Compute stable hashes for exact block comparison:**
   - Partition eligible context (paragraphs, repeated prompt boilerplate, repeated tool/file context blocks) and compute cryptographic hashes (`SHA-256`) over normalized blocks.
3. **Detect repeated blocks within the same request:**
   - Identify identical repeated blocks inside a single prompt, conversation, or multi-file context pack. Keep the canonical occurrence (typically first or highest-priority pinned occurrence) and replace or prune redundant copies with explicit provenance note when needed.
4. **Near-duplicate candidate detection (P1):**
   - Compute 64-bit `SimHash` or `MinHash` signatures over prose/log blocks to flag high-similarity candidates (e.g., nearly identical repeated error dumps or slightly reworded boilerplate instructions).
5. **Safety verification before removal:**
   - Remove a duplicate or near-duplicate candidate **only** when safe for the detected `ContentType` and mode.

---

## 2. Critical Safety Rules

1. **Never deduplicate code or structured data on surface similarity alone:**
   - Two functions, unit tests, or JSON objects can look textually similar while differing in one critical identifier, operator, or parameter value.
   - `source_code`, `json`, and `tool_result` contracts are exempt from near-duplicate removal unless an exact block match is verified non-destructive (e.g., identical duplicated file attachments with matching `file_hash` and line range).
2. **Pinned items are exempt:**
   - User-pinned files or explicit constraint clauses are never pruned as duplicates of unpinned context.
3. **Project- and version-scoped `context_fingerprints`:**
   - All persistent fingerprints stored in SQLite (`context_fingerprints`) are keyed by `(project_id, content_version, block_hash)`.
   - Never share deduplication caches across distinct projects/repositories (prevents cross-project leakage and stale context poisoning).
   - Invalidate fingerprints automatically whenever `file_hash` or `content_version` changes.
4. **Privacy caveat on hashes:**
   - Locally stored deduplication hashes are internal lookup keys only and must **not** be exported as "anonymized telemetry" (per Section 17, low-entropy hashes do not guarantee anonymization).
