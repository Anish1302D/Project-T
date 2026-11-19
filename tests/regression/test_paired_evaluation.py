"""Regression test verifying paired evaluation invariant parity and P1/P2 safe defaults."""

from pathlib import Path

from benchmarks.evaluation.paired_evaluator import run_paired_evaluation


def test_paired_evaluation_zero_degradation_and_safe_defaults(tmp_path: Path) -> None:
    report = run_paired_evaluation(output_dir=tmp_path)
    summary = report["summary"]
    audit = report["p1_p2_feature_audit"]

    assert summary["total_cases"] >= 15
    assert summary["objective_degradation_cases"] == 0
    assert summary["negative_savings_cases"] == 0
    assert summary["median_reduction_pct_eligible"] >= 15.0
    assert summary["median_latency_ms"] < 100.0
    assert audit["ai_semantic_compression_enabled_by_default"] is False
    assert audit["pgvector_enabled"] is False
    assert (tmp_path / "paired-evaluation-report.json").exists()
    assert (tmp_path / "paired-evaluation-report.md").exists()
