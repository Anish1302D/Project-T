# Project T Core Engine Benchmark Report

- **Engine version:** `0.1.0`
- **Dataset version:** `2026-11-v1`
- **Tokenizer target:** `openai:gpt-4o`
- **Default mode:** `balanced`
- **Reference hardware:** `Windows-11-10.0.26200-SP0` (`AMD64`, `14` CPUs, Python `3.14.7`)

> **Note:** Deterministic offline/local benchmark report. Diagnostic quality_score is not proof of downstream LLM equivalence; paired LLM evaluations are tracked separately.

## Category Summary

| Category | Samples | Validated | Fallbacks | Zero/Neg Savings | Assertions Pass | Constraints | Identifiers | Median Red. (All) | Median Red. (Eligible) | p50 Latency (ms) | p95 Latency (ms) |
|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| prompt | 5 | 3 | 2 | 2 | 100.0% | 100.0% | 100.0% | 39.24% | 45.95% | 1.292 | 3.460 |
| constraint | 4 | 4 | 0 | 0 | 100.0% | 100.0% | 100.0% | 13.57% | 13.57% | 2.104 | 2.180 |
| code | 4 | 3 | 1 | 1 | 100.0% | 100.0% | 100.0% | 4.88% | 4.88% | 1.246 | 3.430 |
| conversation | 2 | 2 | 0 | 0 | 100.0% | 100.0% | 100.0% | 25.55% | 25.55% | 2.146 | 2.460 |
| log | 2 | 2 | 0 | 0 | 100.0% | 100.0% | 100.0% | 69.48% | 69.48% | 2.923 | 3.820 |
| repository | 2 | 2 | 0 | 0 | 100.0% | 100.0% | 100.0% | 16.66% | 16.66% | 1.850 | 2.460 |
| api | 4 | 3 | 1 | 1 | 100.0% | 100.0% | 100.0% | 14.52% | 15.09% | 7.692 | 9.740 |
| latency | 3 | 3 | 0 | 0 | 100.0% | 100.0% | 100.0% | 20.59% | 20.59% | 1.209 | 1.250 |

## Per-Case Details

| Category | Case ID | Eligible | Original | Optimized | Saved | Red. % | Accuracy | Status | Latency (ms) | Assertions |
|---|---|---:|---:|---:|---:|---:|---|---|---:|---:|
| prompt | `prompt_001` | True | 79 | 48 | 31 | 39.24% | `exact` | `validated` | 3.946 | PASS |
| prompt | `prompt_002` | True | 74 | 35 | 39 | 52.70% | `exact` | `validated` | 1.500 | PASS |
| prompt | `prompt_003` | True | 74 | 40 | 34 | 45.95% | `exact` | `validated` | 1.292 | PASS |
| prompt | `prompt_004_concise` | False | 15 | 15 | 0 | 0.00% | `exact` | `fallback_no_savings` | 0.577 | PASS |
| prompt | `prompt_005_json_dense` | False | 23 | 23 | 0 | 0.00% | `exact` | `fallback_no_savings` | 0.594 | PASS |
| constraint | `constraint_001` | True | 37 | 32 | 5 | 13.51% | `exact` | `validated` | 2.186 | PASS |
| constraint | `constraint_002` | True | 44 | 38 | 6 | 13.64% | `exact` | `validated` | 2.168 | PASS |
| constraint | `constraint_003` | True | 57 | 53 | 4 | 7.02% | `exact` | `validated` | 2.041 | PASS |
| constraint | `constraint_004` | True | 53 | 44 | 9 | 16.98% | `exact` | `validated` | 2.038 | PASS |
| code | `code_001` | True | 103 | 98 | 5 | 4.85% | `exact` | `validated` | 3.791 | PASS |
| code | `code_002` | True | 56 | 56 | 0 | 0.00% | `exact` | `fallback_no_savings` | 1.093 | PASS |
| code | `code_003` | True | 61 | 58 | 3 | 4.92% | `exact` | `validated` | 1.369 | PASS |
| code | `code_004` | True | 41 | 38 | 3 | 7.32% | `exact` | `validated` | 1.123 | PASS |
| conversation | `conv_001` | True | 153 | 100 | 53 | 34.64% | `exact` | `validated` | 2.497 | PASS |
| conversation | `conv_002` | True | 85 | 71 | 14 | 16.47% | `exact` | `validated` | 1.794 | PASS |
| log | `log_001` | True | 485 | 124 | 361 | 74.43% | `exact` | `validated` | 3.917 | PASS |
| log | `log_002` | True | 265 | 94 | 171 | 64.53% | `exact` | `validated` | 1.929 | PASS |
| repository | `repo_001` | True | 80 | 64 | 16 | 20.00% | `exact` | `validated` | 2.529 | PASS |
| repository | `repo_002` | True | 75 | 65 | 10 | 13.33% | `exact` | `validated` | 1.171 | PASS |
| api | `api_001_openai_verbose` | True | 251 | 216 | 35 | 13.94% | `exact` | `validated` | 10.102 | PASS |
| api | `api_002_anthropic_tools` | True | 324 | 256 | 68 | 20.99% | `exact` | `validated` | 7.711 | PASS |
| api | `api_003_google_structured` | True | 285 | 242 | 43 | 15.09% | `exact` | `validated` | 7.673 | PASS |
| api | `api_004_openai_concise_guard` | False | 33 | 33 | 0 | 0.00% | `exact` | `fallback_no_savings` | 6.111 | PASS |
| latency | `latency_small_1_1` | True | 34 | 27 | 7 | 20.59% | `exact` | `validated` | 1.209 | PASS |
| latency | `latency_small_2_2` | True | 34 | 27 | 7 | 20.59% | `exact` | `validated` | 0.842 | PASS |
| latency | `latency_medium_3` | True | 66 | 35 | 31 | 46.97% | `exact` | `validated` | 1.259 | PASS |
