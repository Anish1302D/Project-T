"""Regression check validating the reproducible benchmark suite and acceptance targets."""

import statistics
from pathlib import Path

from benchmarks.runner.run_benchmarks import run_benchmark_suite


def test_benchmark_suite_meets_phase_3_engine_targets(tmp_path: Path) -> None:
    report = run_benchmark_suite(output_dir=tmp_path)
    by_cat = {c["category"]: c for c in report["categories"]}

    # 100% assertion, constraint, and identifier preservation across curated datasets
    for cat_name, summary in by_cat.items():
        assert summary["assertion_pass_rate"] == 1.0, f"{cat_name} assertion failures"
        assert summary["constraint_preservation_rate"] == 1.0, f"{cat_name} constraint failures"
        assert summary["identifier_preservation_rate"] == 1.0, f"{cat_name} identifier failures"
        assert summary["structure_pass_rate"] == 1.0, f"{cat_name} structure failures"

    # Overall eligible benchmark inputs achieve >= 15% median token reduction (Section 16)
    eligible_reductions = [
        c["reduction_percentage"] for c in report["cases"] if c["eligible"]
    ]
    assert statistics.median(eligible_reductions) >= 15.0

    # High-redundancy eligible categories achieve >= 15% median reduction individually
    for eligible_cat in ("prompt", "log", "conversation", "repository"):
        assert by_cat[eligible_cat]["median_reduction_pct_eligible"] >= 15.0

    # Small-input local latency meets < 100 ms target
    assert by_cat["latency"]["p95_latency_ms"] < 100.0

    assert (tmp_path / "baseline-report.json").exists()
    assert (tmp_path / "baseline-report.md").exists()
