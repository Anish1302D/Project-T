"""Controlled soak stability & latency availability test for Local Runtime (target >= 99% uptime)."""

from __future__ import annotations

import statistics
import time
from pathlib import Path

from fastapi.testclient import TestClient

from project_t_local_runtime import LocalRuntimeService, RuntimeConfig, create_app


def _percentile(sorted_vals: list[float], pct: float) -> float:
    idx = (len(sorted_vals) - 1) * (pct / 100.0)
    lo = int(idx)
    hi = min(lo + 1, len(sorted_vals) - 1)
    frac = idx - lo
    return sorted_vals[lo] * (1 - frac) + sorted_vals[hi] * frac


def test_local_runtime_controlled_soak_stability_and_latency(tmp_path: Path) -> None:
    service = LocalRuntimeService(
        config=RuntimeConfig(
            data_dir=tmp_path / "soak_rt",
            use_os_keyring=False,
            allow_tiktoken=True,
            rate_limit_requests=1000,
            rate_limit_window_seconds=60,
        )
    )
    app = create_app(service=service)
    headers = {"Authorization": f"Bearer {service.credentials.bearer_token}"}

    prompts = [
        (
            "Hello, could you please review `verifyJwtToken` in order to fix the 401 timeout?\n\n"
            "Rule: Never alter database schema.\n\nRule: Never alter database schema."
        ),
        "Explain HTTP 429 cleanly.",
        "ERROR db_pool exhausted\nERROR db_pool exhausted\nERROR db_pool exhausted\nINFO ready",
    ]

    total_ops = 120
    success_count = 0
    small_latencies_ms: list[float] = []

    with TestClient(app) as client:
        for i in range(total_ops):
            t0 = time.perf_counter()
            if i % 4 == 0:
                resp = client.get("/api/v1/health")
            elif i % 4 == 1:
                resp = client.post(
                    "/api/v1/optimize",
                    json={"content": prompts[i % 2], "provider": "openai", "model": "gpt-4o"},
                    headers=headers,
                )
                small_latencies_ms.append((time.perf_counter() - t0) * 1000.0)
            elif i % 4 == 2:
                resp = client.post(
                    "/api/v1/logs/compress",
                    json={"output": prompts[2], "provider": "openai", "model": "gpt-4o"},
                    headers=headers,
                )
            else:
                resp = client.get("/api/v1/metrics", headers=headers)

            if resp.status_code == 200:
                success_count += 1

        # Verify health & availability threshold (>= 99%)
        availability = success_count / total_ops
        assert availability >= 0.99
        assert success_count == total_ops

        health = client.get("/api/v1/health").json()
        assert health["status"] == "ok"
        assert health["sqlite_ready"] is True

    p95_ms = _percentile(sorted(small_latencies_ms), 95.0)
    p50_ms = statistics.median(small_latencies_ms)
    assert p50_ms < 100.0
    assert p95_ms < 100.0
