"""Multi-device analytics rollup aggregator backing all 10 Dashboard views."""

from __future__ import annotations

import statistics
from collections import defaultdict
from datetime import UTC, datetime
from typing import Any, Literal


def _parse_dt(raw: str) -> datetime:
    cleaned = raw.strip()
    if cleaned.endswith("Z"):
        cleaned = cleaned[:-1] + "+00:00"
    try:
        dt = datetime.fromisoformat(cleaned)
    except ValueError:
        dt = datetime.strptime(cleaned[:19], "%Y-%m-%d %H:%M:%S")
    if dt.tzinfo is None:
        return dt.replace(tzinfo=UTC)
    return dt.astimezone(UTC)


def _percentile(sorted_vals: list[float], pct: float) -> float:
    if not sorted_vals:
        return 0.0
    if len(sorted_vals) == 1:
        return round(sorted_vals[0], 2)
    idx = (len(sorted_vals) - 1) * (pct / 100.0)
    lo = int(idx)
    hi = min(lo + 1, len(sorted_vals) - 1)
    frac = idx - lo
    return round(sorted_vals[lo] * (1 - frac) + sorted_vals[hi] * frac, 2)


def _bucket_for_dt(dt: datetime, granularity: Literal["daily", "weekly", "monthly"]) -> str:
    if granularity == "monthly":
        return dt.strftime("%Y-%m")
    if granularity == "weekly":
        iso_year, iso_week, _ = dt.isocalendar()
        return f"{iso_year}-W{iso_week:02d}"
    return dt.strftime("%Y-%m-%d")


def compute_analytics_overview(
    *,
    rows: list[dict[str, Any]],
    benchmarks: list[dict[str, Any]],
    devices: list[dict[str, Any]],
    granularity: Literal["daily", "weekly", "monthly"] = "daily",
    start_date: str | None = None,
    end_date: str | None = None,
) -> dict[str, Any]:
    """Compute all 10 required dashboard analytics panels with strict accuracy separation."""
    start_day = start_date[:10] if start_date else None
    end_day = end_date[:10] if end_date else None

    filtered: list[tuple[datetime, dict[str, Any]]] = []
    for row in rows:
        dt = _parse_dt(row["created_at"])
        day_str = dt.strftime("%Y-%m-%d")
        if start_day and day_str < start_day:
            continue
        if end_day and day_str > end_day:
            continue
        filtered.append((dt, row))

    total_orig = sum(int(r["original_tokens"]) for _, r in filtered)
    total_opt = sum(int(r["optimized_tokens"]) for _, r in filtered)
    total_saved = sum(int(r["tokens_saved"]) for _, r in filtered)
    n_runs = len(filtered)
    net_reduction_pct = round((total_saved / total_orig) * 100.0, 2) if total_orig > 0 else 0.0

    # View 2 & 3: Accuracy & cost avoided separation (never conflating estimated vs exact vs confirmed)
    exact_runs = 0
    exact_saved = 0
    estimated_runs = 0
    estimated_saved = 0
    provider_confirmed_runs = 0
    provider_confirmed_input_tokens = 0
    provider_confirmed_saved = 0
    est_cost_usd = 0.0
    conf_cost_usd = 0.0
    pricing_versions: set[str] = set()

    # View 4-8 aggregations
    prov_model_buckets: dict[tuple[str, str], dict[str, Any]] = {}
    integration_buckets: dict[str, dict[str, Any]] = {}
    trend_buckets: dict[str, dict[str, Any]] = {}
    mode_counts: dict[str, dict[str, Any]] = {}
    method_counts: dict[str, int] = defaultdict(int)
    status_counts: dict[str, int] = defaultdict(int)
    latencies: list[float] = []

    for dt, r in filtered:
        saved = int(r["tokens_saved"])
        orig = int(r["original_tokens"])
        opt = int(r["optimized_tokens"])
        acc = str(r["accuracy"])
        est_c = float(r.get("estimated_cost_avoided_usd") or 0.0)
        conf_c = r.get("provider_confirmed_cost_avoided_usd")
        est_cost_usd += est_c
        if conf_c is not None:
            conf_cost_usd += float(conf_c)
        if r.get("pricing_version"):
            pricing_versions.add(str(r["pricing_version"]))

        if acc == "exact":
            exact_runs += 1
            exact_saved += saved
        else:
            estimated_runs += 1
            estimated_saved += saved

        conf_in = r.get("provider_confirmed_input_tokens")
        conf_orig = r.get("provider_confirmed_original_tokens")
        if conf_in is not None:
            provider_confirmed_runs += 1
            provider_confirmed_input_tokens += int(conf_in)
            if conf_orig is not None:
                provider_confirmed_saved += max(0, int(conf_orig) - int(conf_in))
            elif acc == "exact" and orig > 0:
                provider_confirmed_saved += max(0, orig - int(conf_in))

        # Provider + Model
        pm_key = (str(r["provider"]), str(r["model_name"]))
        pm = prov_model_buckets.setdefault(
            pm_key,
            {
                "provider": pm_key[0],
                "model": pm_key[1],
                "runs": 0,
                "original_tokens": 0,
                "optimized_tokens": 0,
                "tokens_saved": 0,
                "exact_runs": 0,
                "estimated_runs": 0,
                "estimated_cost_avoided_usd": 0.0,
                "confirmed_cost_avoided_usd": 0.0,
            },
        )
        pm["runs"] += 1
        pm["original_tokens"] += orig
        pm["optimized_tokens"] += opt
        pm["tokens_saved"] += saved
        pm["exact_runs" if acc == "exact" else "estimated_runs"] += 1
        pm["estimated_cost_avoided_usd"] += est_c
        if conf_c is not None:
            pm["confirmed_cost_avoided_usd"] += float(conf_c)

        # Integration
        integ = str(r["integration"])
        ib = integration_buckets.setdefault(
            integ,
            {
                "integration": integ,
                "runs": 0,
                "original_tokens": 0,
                "optimized_tokens": 0,
                "tokens_saved": 0,
                "estimated_cost_avoided_usd": 0.0,
            },
        )
        ib["runs"] += 1
        ib["original_tokens"] += orig
        ib["optimized_tokens"] += opt
        ib["tokens_saved"] += saved
        ib["estimated_cost_avoided_usd"] += est_c

        # Trend bucket
        tb_key = _bucket_for_dt(dt, granularity)
        tb = trend_buckets.setdefault(
            tb_key,
            {
                "bucket": tb_key,
                "runs": 0,
                "original_tokens": 0,
                "optimized_tokens": 0,
                "tokens_saved": 0,
                "exact_saved": 0,
                "estimated_saved": 0,
                "estimated_cost_avoided_usd": 0.0,
            },
        )
        tb["runs"] += 1
        tb["original_tokens"] += orig
        tb["optimized_tokens"] += opt
        tb["tokens_saved"] += saved
        if acc == "exact":
            tb["exact_saved"] += saved
        else:
            tb["estimated_saved"] += saved
        tb["estimated_cost_avoided_usd"] += est_c

        # Mode & Methods
        mode_key = str(r["optimization_mode"])
        mb = mode_counts.setdefault(mode_key, {"mode": mode_key, "runs": 0, "tokens_saved": 0})
        mb["runs"] += 1
        mb["tokens_saved"] += saved
        for method in r.get("methods", []):
            method_counts[str(method)] += 1

        # Validation statuses & latency
        status_counts[str(r["status"])] += 1
        latencies.append(float(r["duration_ms"]))

    for pm in prov_model_buckets.values():
        pm["reduction_percentage"] = (
            round((pm["tokens_saved"] / pm["original_tokens"]) * 100.0, 2)
            if pm["original_tokens"] > 0
            else 0.0
        )
        pm["estimated_cost_avoided_usd"] = round(pm["estimated_cost_avoided_usd"], 6)
        pm["confirmed_cost_avoided_usd"] = round(pm["confirmed_cost_avoided_usd"], 6)

    for ib in integration_buckets.values():
        ib["reduction_percentage"] = (
            round((ib["tokens_saved"] / ib["original_tokens"]) * 100.0, 2)
            if ib["original_tokens"] > 0
            else 0.0
        )
        ib["estimated_cost_avoided_usd"] = round(ib["estimated_cost_avoided_usd"], 6)

    for tb in trend_buckets.values():
        tb["estimated_cost_avoided_usd"] = round(tb["estimated_cost_avoided_usd"], 6)

    validated_runs = status_counts.get("validated", 0)
    f_val = status_counts.get("fallback_validation_failed", 0)
    f_no = status_counts.get("fallback_no_savings", 0)
    f_err = status_counts.get("fallback_error", 0)
    fallback_total = f_val + f_no + f_err
    fallback_rate_pct = round((fallback_total / n_runs) * 100.0, 2) if n_runs > 0 else 0.0
    validation_failure_rate_pct = round((f_val / n_runs) * 100.0, 2) if n_runs > 0 else 0.0

    sorted_lat = sorted(latencies)
    latency_summary = {
        "sample_count": n_runs,
        "p50_ms": _percentile(sorted_lat, 50),
        "p90_ms": _percentile(sorted_lat, 90),
        "p95_ms": _percentile(sorted_lat, 95),
        "p99_ms": _percentile(sorted_lat, 99),
        "avg_ms": round(statistics.mean(sorted_lat), 2) if sorted_lat else 0.0,
    }

    return {
        "privacy_guarantee": "metadata_only_no_raw_prompts",
        "totals": {
            "total_runs": n_runs,
            "original_tokens": total_orig,
            "optimized_tokens": total_opt,
            "tokens_saved": total_saved,
            "reduction_percentage": net_reduction_pct,
        },
        "accuracy_breakdown": {
            "exact_runs": exact_runs,
            "exact_tokens_saved": exact_saved,
            "estimated_runs": estimated_runs,
            "estimated_tokens_saved": estimated_saved,
            "provider_confirmed_runs": provider_confirmed_runs,
            "provider_confirmed_input_tokens": provider_confirmed_input_tokens,
            "provider_confirmed_tokens_saved": provider_confirmed_saved,
        },
        "cost_avoided": {
            "estimated_cost_avoided_usd": round(est_cost_usd, 6),
            "provider_confirmed_cost_avoided_usd": round(conf_cost_usd, 6),
            "pricing_versions": sorted(pricing_versions),
        },
        "by_provider_model": sorted(
            prov_model_buckets.values(), key=lambda x: x["tokens_saved"], reverse=True
        ),
        "by_integration": sorted(
            integration_buckets.values(), key=lambda x: x["runs"], reverse=True
        ),
        "trends": [trend_buckets[k] for k in sorted(trend_buckets.keys())],
        "granularity": granularity,
        "modes_and_methods": {
            "by_mode": sorted(mode_counts.values(), key=lambda x: x["runs"], reverse=True),
            "by_method": [
                {"method": m, "count": c}
                for m, c in sorted(method_counts.items(), key=lambda kv: kv[1], reverse=True)
            ],
        },
        "validation": {
            "validated_runs": validated_runs,
            "fallback_validation_failed": f_val,
            "fallback_no_savings": f_no,
            "fallback_error": f_err,
            "fallback_total": fallback_total,
            "fallback_rate_pct": fallback_rate_pct,
            "validation_failure_rate_pct": validation_failure_rate_pct,
        },
        "benchmarks": benchmarks,
        "latency": latency_summary,
        "devices": devices,
    }
