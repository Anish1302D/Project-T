# Project T Paired Evaluation & P1/P2 Audit Report

- **Evaluation mode:** `offline_paired_invariant_and_assertion_audit`
- **Fixed target model:** `openai:gpt-4o`
- **Live LLM trials executed:** `False`
> **Transparency Note:** Executed deterministically offline without live external LLM API keys. Behavioral invariance (objective assertions, constraints, identifiers) and exact BPE token counts are measured directly; downstream LLM answer grading requires live provider keys.

## Summary

- Total paired cases: `21` (`18` eligible)
- Validated optimized cases: `17`
- Fallback / no-savings cases: `4`
- Negative savings cases accepted: `0`
- Objective assertion/constraint/identifier degradations: `0`
- Median token reduction (eligible): `15.78%`
- Median optimization latency: `0.790 ms`

## P1 / P2 Feature Justification Audit

- `allow_ai_semantic_compression` default: `False`
- `pgvector` enabled: `False`
- Advisory P1 SimHash near-duplicate pairs observed: `6`
- Recommendation: Keep allow_ai_semantic_compression=False and pgvector deferred: deterministic stages already meet >=15% eligible median reduction without external LLM compression cost.

## Per-Case Results

| Category | Case ID | Eligible | Orig | Opt | Saved | Red. % | Status | Control OK | Treatment OK | Constraints | Identifiers |
|---|---|---:|---:|---:|---:|---:|---|---:|---:|---:|---:|
| prompt | `prompt_001` | True | 79 | 48 | 31 | 39.24% | `validated` | True | True | True | True |
| prompt | `prompt_002` | True | 74 | 35 | 39 | 52.70% | `validated` | True | True | True | True |
| prompt | `prompt_003` | True | 74 | 40 | 34 | 45.95% | `validated` | True | True | True | True |
| prompt | `prompt_004_concise` | False | 15 | 15 | 0 | 0.00% | `fallback_no_savings` | True | True | True | True |
| prompt | `prompt_005_json_dense` | False | 23 | 23 | 0 | 0.00% | `fallback_no_savings` | True | True | True | True |
| constraint | `constraint_001` | True | 37 | 32 | 5 | 13.51% | `validated` | True | True | True | True |
| constraint | `constraint_002` | True | 44 | 38 | 6 | 13.64% | `validated` | True | True | True | True |
| constraint | `constraint_003` | True | 57 | 53 | 4 | 7.02% | `validated` | True | True | True | True |
| constraint | `constraint_004` | True | 53 | 44 | 9 | 16.98% | `validated` | True | True | True | True |
| code | `code_001` | True | 103 | 98 | 5 | 4.85% | `validated` | True | True | True | True |
| code | `code_002` | True | 56 | 56 | 0 | 0.00% | `fallback_no_savings` | True | True | True | True |
| code | `code_003` | True | 61 | 58 | 3 | 4.92% | `validated` | True | True | True | True |
| code | `code_004` | True | 41 | 38 | 3 | 7.32% | `validated` | True | True | True | True |
| conversation | `conv_001` | True | 153 | 100 | 53 | 34.64% | `validated` | True | True | True | True |
| conversation | `conv_002` | True | 85 | 71 | 14 | 16.47% | `validated` | True | True | True | True |
| log | `log_001` | True | 485 | 124 | 361 | 74.43% | `validated` | True | True | True | True |
| log | `log_002` | True | 265 | 94 | 171 | 64.53% | `validated` | True | True | True | True |
| api | `api_001_openai_verbose` | True | 251 | 216 | 35 | 13.94% | `validated` | True | True | True | True |
| api | `api_002_anthropic_tools` | True | 324 | 256 | 68 | 20.99% | `validated` | True | True | True | True |
| api | `api_003_google_structured` | True | 285 | 242 | 43 | 15.09% | `validated` | True | True | True | True |
| api | `api_004_openai_concise_guard` | False | 33 | 33 | 0 | 0.00% | `fallback_no_savings` | True | True | True | True |
