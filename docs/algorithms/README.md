# Optimization Algorithms Specification

This directory defines the deterministic-first, quality-aware optimization algorithms inside `packages/optimization-core`.

## Index

| Document | Scope |
|---|---|
| [Pipeline & Policy Modes](./pipeline-and-modes.md) | P0/P1/P2 algorithm portfolio, `safe`/`balanced`/`aggressive` policy matrix, ordering, and fallback thresholds |
| [Classification & Constraint Extraction](./classification-and-constraints.md) | Content classification, structured constraint extraction, and the 10 protected-span categories |
| [Deduplication & Similarity](./deduplication.md) | 5-stage deduplication strategy, stable block hashing, SimHash/MinHash near-duplicates, and project/version fingerprint scoping |
| [Compression & Context Selection](./compression-and-context-selection.md) | Whitespace normalization, rule-based compression, terminal log extraction, BM25/FTS context selection, conversation compaction, and optional AI compression |
| [Token Accounting & Quality Scoring](./token-accounting-and-quality-scoring.md) | Savings formula, `exact` vs `estimated` rules, diagnostic quality score `Q`, and `QualityValidator` hard checks |
