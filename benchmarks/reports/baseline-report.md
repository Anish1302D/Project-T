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
| prompt | 5 | 3 | 2 | 2 | 100.0% | 100.0% | 100.0% | 39.24% | 45.95% | 0.540 | 1.190 |
| constraint | 4 | 4 | 0 | 0 | 100.0% | 100.0% | 100.0% | 13.57% | 13.57% | 0.497 | 0.530 |
| code | 4 | 3 | 1 | 1 | 100.0% | 100.0% | 100.0% | 4.88% | 4.88% | 0.453 | 1.090 |
| conversation | 2 | 2 | 0 | 0 | 100.0% | 100.0% | 100.0% | 25.55% | 25.55% | 1.213 | 1.420 |
| log | 2 | 2 | 0 | 0 | 100.0% | 100.0% | 100.0% | 69.48% | 69.48% | 1.030 | 1.250 |
| repository | 2 | 2 | 0 | 0 | 100.0% | 100.0% | 100.0% | 16.66% | 16.66% | 0.722 | 0.970 |
| latency | 3 | 3 | 0 | 0 | 100.0% | 100.0% | 100.0% | 20.59% | 20.59% | 0.415 | 0.470 |

## Per-Case Details

| Category | Case ID | Eligible | Original | Optimized | Saved | Red. % | Accuracy | Status | Latency (ms) | Assertions |
|---|---|---:|---:|---:|---:|---:|---|---|---:|---:|
| prompt | `prompt_001` | True | 79 | 48 | 31 | 39.24% | `exact` | `validated` | 1.326 | PASS |
| prompt | `prompt_002` | True | 74 | 35 | 39 | 52.70% | `exact` | `validated` | 0.643 | PASS |
| prompt | `prompt_003` | True | 74 | 40 | 34 | 45.95% | `exact` | `validated` | 0.540 | PASS |
| prompt | `prompt_004_concise` | False | 15 | 15 | 0 | 0.00% | `exact` | `fallback_no_savings` | 0.234 | PASS |
| prompt | `prompt_005_json_dense` | False | 23 | 23 | 0 | 0.00% | `exact` | `fallback_no_savings` | 0.251 | PASS |
| constraint | `constraint_001` | True | 37 | 32 | 5 | 13.51% | `exact` | `validated` | 0.431 | PASS |
| constraint | `constraint_002` | True | 44 | 38 | 6 | 13.64% | `exact` | `validated` | 0.527 | PASS |
| constraint | `constraint_003` | True | 57 | 53 | 4 | 7.02% | `exact` | `validated` | 0.526 | PASS |
| constraint | `constraint_004` | True | 53 | 44 | 9 | 16.98% | `exact` | `validated` | 0.468 | PASS |
| code | `code_001` | True | 103 | 98 | 5 | 4.85% | `exact` | `validated` | 1.195 | PASS |
| code | `code_002` | True | 56 | 56 | 0 | 0.00% | `exact` | `fallback_no_savings` | 0.410 | PASS |
| code | `code_003` | True | 61 | 58 | 3 | 4.92% | `exact` | `validated` | 0.489 | PASS |
| code | `code_004` | True | 41 | 38 | 3 | 7.32% | `exact` | `validated` | 0.416 | PASS |
| conversation | `conv_001` | True | 153 | 100 | 53 | 34.64% | `exact` | `validated` | 0.986 | PASS |
| conversation | `conv_002` | True | 85 | 71 | 14 | 16.47% | `exact` | `validated` | 1.440 | PASS |
| log | `log_001` | True | 485 | 124 | 361 | 74.43% | `exact` | `validated` | 1.270 | PASS |
| log | `log_002` | True | 265 | 94 | 171 | 64.53% | `exact` | `validated` | 0.790 | PASS |
| repository | `repo_001` | True | 80 | 64 | 16 | 20.00% | `exact` | `validated` | 0.993 | PASS |
| repository | `repo_002` | True | 75 | 65 | 10 | 13.33% | `exact` | `validated` | 0.450 | PASS |
| latency | `latency_small_1_1` | True | 34 | 27 | 7 | 20.59% | `exact` | `validated` | 0.415 | PASS |
| latency | `latency_small_2_2` | True | 34 | 27 | 7 | 20.59% | `exact` | `validated` | 0.330 | PASS |
| latency | `latency_medium_3` | True | 66 | 35 | 31 | 46.97% | `exact` | `validated` | 0.477 | PASS |
