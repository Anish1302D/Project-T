"""CLI and programmatic benchmark runner generating JSON & Markdown reports."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
for pkg_src in (
    ROOT / "packages" / "contracts" / "src",
    ROOT / "packages" / "optimization-core" / "src",
    ROOT / "packages" / "provider-adapters" / "src",
    ROOT,
):
    if str(pkg_src) not in sys.path:
        sys.path.insert(0, str(pkg_src))

from benchmarks.evaluation.evaluator import BenchmarkEvaluator  # noqa: E402
from project_t_contracts import OptimizationMode  # noqa: E402


def render_markdown_report(report: dict) -> str:
    hw = report["hardware"]
    lines = [
        "# Project T Core Engine Benchmark Report",
        "",
        f"- **Engine version:** `{report['engine_version']}`",
        f"- **Dataset version:** `{report['dataset_version']}`",
        f"- **Tokenizer target:** `{report['provider']}:{report['model']}`",
        f"- **Default mode:** `{report['default_mode']}`",
        f"- **Reference hardware:** `{hw['os_platform']}` (`{hw['machine']}`, `{hw['cpu_count']}` CPUs, Python `{hw['python_version']}`)",
        "",
        f"> **Note:** {report['note']}",
        "",
        "## Category Summary",
        "",
        "| Category | Samples | Validated | Fallbacks | Zero/Neg Savings | Assertions Pass | Constraints | Identifiers | Median Red. (All) | Median Red. (Eligible) | p50 Latency (ms) | p95 Latency (ms) |",
        "|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|",
    ]
    for cat in report["categories"]:
        lines.append(
            f"| {cat['category']} | {cat['sample_count']} | {cat['validated_count']} | "
            f"{cat['fallback_count']} | {cat['negative_or_zero_savings_count']} | "
            f"{cat['assertion_pass_rate'] * 100:.1f}% | {cat['constraint_preservation_rate'] * 100:.1f}% | "
            f"{cat['identifier_preservation_rate'] * 100:.1f}% | {cat['median_reduction_pct_all']:.2f}% | "
            f"{cat['median_reduction_pct_eligible']:.2f}% | {cat['p50_latency_ms']:.3f} | {cat['p95_latency_ms']:.3f} |"
        )
    lines.extend(["", "## Per-Case Details", ""])
    lines.append("| Category | Case ID | Eligible | Original | Optimized | Saved | Red. % | Accuracy | Status | Latency (ms) | Assertions |")
    lines.append("|---|---|---:|---:|---:|---:|---:|---|---|---:|---:|")
    for case in report["cases"]:
        lines.append(
            f"| {case['category']} | `{case['case_id']}` | {case['eligible']} | "
            f"{case['original_tokens']} | {case['optimized_tokens']} | {case['tokens_saved']} | "
            f"{case['reduction_percentage']:.2f}% | `{case['accuracy']}` | `{case['status']}` | "
            f"{case['latency_ms']:.3f} | {'PASS' if case['assertions_ok'] else 'FAIL'} |"
        )
    lines.append("")
    return "\n".join(lines)


def run_benchmark_suite(
    *,
    datasets_dir: Path | None = None,
    output_dir: Path | None = None,
    provider: str = "openai",
    model: str = "gpt-4o",
    mode: OptimizationMode = OptimizationMode.BALANCED,
) -> dict:
    ds_dir = datasets_dir if datasets_dir is not None else ROOT / "benchmarks" / "datasets"
    out_dir = output_dir if output_dir is not None else ROOT / "benchmarks" / "reports"
    out_dir.mkdir(parents=True, exist_ok=True)

    evaluator = BenchmarkEvaluator(
        datasets_dir=ds_dir,
        provider=provider,
        model=model,
        default_mode=mode,
    )
    report = evaluator.run_all()

    json_path = out_dir / "baseline-report.json"
    md_path = out_dir / "baseline-report.md"
    json_path.write_text(json.dumps(report, indent=2), encoding="utf-8")
    md_path.write_text(render_markdown_report(report), encoding="utf-8")
    return report


def main() -> int:
    parser = argparse.ArgumentParser(description="Run Project T deterministic engine benchmarks.")
    parser.add_argument("--provider", default="openai")
    parser.add_argument("--model", default="gpt-4o")
    parser.add_argument("--mode", default="balanced", choices=["safe", "balanced", "aggressive"])
    args = parser.parse_args()

    report = run_benchmark_suite(
        provider=args.provider,
        model=args.model,
        mode=OptimizationMode(args.mode),
    )
    print(f"Benchmark run complete: {len(report['categories'])} categories, {len(report['cases'])} cases.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
