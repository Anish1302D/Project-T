"""Integration tests for Cloud Control Plane auth, sync idempotency, rules conflict resolution, and analytics."""

from __future__ import annotations

from pathlib import Path

from fastapi.testclient import TestClient

from project_t_cloud_services import CloudConfig, create_control_plane_app
from project_t_contracts import OptimizationMode, OptimizationRequestWire
from project_t_local_runtime import LocalRuntimeService, RuntimeConfig


def test_cloud_auth_device_pairing_idempotent_sync_and_analytics_rollups(tmp_path: Path) -> None:
    app = create_control_plane_app(
        CloudConfig(
            data_dir=tmp_path / "cloud_data",
            database_url=f"sqlite:///{tmp_path / 'cloud.db'}",
            jwt_secret="integration-test-jwt-secret-key-32bytes",
        )
    )

    local_svc = LocalRuntimeService(
        config=RuntimeConfig(
            data_dir=tmp_path / "local_data",
            db_path=tmp_path / "local.db",
            use_os_keyring=False,
            allow_tiktoken=True,
        )
    )

    try:
        # Produce real metadata run locally
        local_svc.optimize(
            OptimizationRequestWire(
                content=(
                    "Please kindly help inspect `verifyToken` in middleware.py.\n\n"
                    "Rule: Keep HTTP 401 intact.\n\nRule: Keep HTTP 401 intact."
                ),
                provider="openai",
                model="gpt-4o",
                mode=OptimizationMode.BALANCED,
                integration="vscode",
            )
        )
        local_sync_payload = local_svc.build_metadata_sync_payload()
        assert len(local_sync_payload["runs"]) == 1

        with TestClient(app) as client:
            health = client.get("/health")
            assert health.status_code == 200
            assert health.json()["db_ready"] is True
            assert health.json()["database_backend"] == "sqlite"

            # Register & login
            reg = client.post(
                "/api/cloud/v1/auth/register",
                json={
                    "email": "dev@project-t.local",
                    "display_name": "Dev Engineer",
                    "password": "super-secret-password",
                },
            )
            assert reg.status_code == 201
            login = client.post(
                "/api/cloud/v1/auth/login",
                json={"email": "dev@project-t.local", "password": "super-secret-password"},
            )
            assert login.status_code == 200
            user_token = login.json()["access_token"]
            auth_headers = {"Authorization": f"Bearer {user_token}"}

            me = client.get("/api/cloud/v1/auth/me", headers=auth_headers)
            assert me.status_code == 200
            assert me.json()["email"] == "dev@project-t.local"

            # Pair local installation as Laptop-VSCode + another device Workstation-Gateway
            pair_1 = client.post(
                "/api/cloud/v1/auth/devices/pair",
                json={
                    "installation_id": str(local_sync_payload["installation_id"]),
                    "device_id": "dev_laptop",
                    "device_label": "Laptop-VSCode",
                    "os_platform": "Windows 11",
                    "runtime_version": "0.5.0",
                    "sync_enabled": True,
                },
                headers=auth_headers,
            )
            assert pair_1.status_code == 200
            sync_token_1 = pair_1.json()["sync_token"]

            pair_2 = client.post(
                "/api/cloud/v1/auth/devices/pair",
                json={
                    "installation_id": "inst_gateway_box",
                    "device_id": "dev_gateway",
                    "device_label": "Server-Gateway",
                    "os_platform": "Linux",
                    "runtime_version": "0.5.0",
                    "sync_enabled": True,
                },
                headers=auth_headers,
            )
            assert pair_2.status_code == 200

            devices_resp = client.get("/api/cloud/v1/auth/devices", headers=auth_headers)
            assert len(devices_resp.json()["devices"]) == 2

            # Opt-in push from LocalRuntimeService via post_json_fn -> idempotent replay check
            def _post_to_test_client(url: str, payload: dict, token: str):
                path = "/" + url.split("://", 1)[1].split("/", 1)[1]
                r = client.post(path, json=payload, headers={"Authorization": f"Bearer {token}"})
                return r.status_code, r.json()

            push_1 = local_svc.sync_metadata_to_cloud(
                cloud_base_url="http://testserver",
                sync_token=sync_token_1,
                opt_in=True,
                post_json_fn=_post_to_test_client,
            )
            push_2 = local_svc.sync_metadata_to_cloud(
                cloud_base_url="http://testserver",
                sync_token=sync_token_1,
                opt_in=True,
                post_json_fn=_post_to_test_client,
            )
            assert push_1["synced"] is True and push_2["synced"] is True

            # Sync diverse runs on second device including Anthropic estimated, gateway confirmed, and fallback
            gw_sync = client.post(
                "/api/cloud/v1/sync/runs",
                json={
                    "installation_id": "inst_gateway_box",
                    "runs": [
                        {
                            "run_id": "run_gw_1",
                            "request_id": "gw_1",
                            "provider": "anthropic",
                            "model": "claude-sonnet-4",
                            "integration": "gateway",
                            "content_type": "prompt",
                            "optimization_mode": "safe",
                            "status": "validated",
                            "methods": ["whitespace_normalization", "exact_paragraph_dedup"],
                            "warnings": [],
                            "quality_score": 0.96,
                            "duration_ms": 14,
                            "original_tokens": 500,
                            "optimized_tokens": 350,
                            "tokens_saved": 150,
                            "reduction_percentage": 30.0,
                            "accuracy": "estimated",
                            "provider_confirmed_original_tokens": 495,
                            "provider_confirmed_input_tokens": 345,
                            "pricing_version": "2026-11-v1",
                            "estimated_cost_avoided_usd": 0.00045,
                            "provider_confirmed_cost_avoided_usd": 0.00045,
                            "created_at": "2026-11-18T10:00:00Z",
                        },
                        {
                            "run_id": "run_gw_2",
                            "request_id": "gw_2",
                            "provider": "openai",
                            "model": "gpt-4o",
                            "integration": "gateway",
                            "content_type": "prompt",
                            "optimization_mode": "aggressive",
                            "status": "fallback_validation_failed",
                            "methods": [],
                            "warnings": ["constraint_missing"],
                            "quality_score": 0.4,
                            "duration_ms": 22,
                            "original_tokens": 120,
                            "optimized_tokens": 120,
                            "tokens_saved": 0,
                            "reduction_percentage": 0.0,
                            "accuracy": "exact",
                            "pricing_version": "2026-11-v1",
                            "estimated_cost_avoided_usd": 0.0,
                            "created_at": "2026-11-19T08:00:00Z",
                        },
                    ],
                },
                headers=auth_headers,
            )
            assert gw_sync.status_code == 200
            assert gw_sync.json()["upserted"] == 2

            # Sync rules with monotonic version conflict resolution
            r_v2 = client.post(
                "/api/cloud/v1/sync/rules",
                json={
                    "rule_id": "global_default",
                    "installation_id": "inst_gateway_box",
                    "scope": "global",
                    "mode": "balanced",
                    "preserve_identifiers": True,
                    "allow_ai_semantic_compression": False,
                    "min_meaningful_savings_tokens": 15,
                    "rules": {"skip_short_tokens": 25},
                    "version": 2,
                    "prefer_local_override": False,
                },
                headers=auth_headers,
            )
            assert r_v2.status_code == 200 and r_v2.json()["resolution"] == "applied"

            r_stale = client.post(
                "/api/cloud/v1/sync/rules",
                json={
                    "rule_id": "global_default",
                    "installation_id": "inst_gateway_box",
                    "scope": "global",
                    "mode": "safe",
                    "version": 1,
                    "prefer_local_override": False,
                },
                headers=auth_headers,
            )
            assert r_stale.status_code == 200
            assert r_stale.json()["resolution"] == "conflict_cloud_newer"
            assert r_stale.json()["rule"]["version"] == 2

            # Sync benchmark summary
            bench = client.post(
                "/api/cloud/v1/sync/benchmarks",
                json={
                    "installation_id": "inst_gateway_box",
                    "results": [
                        {
                            "id": "bench_api_v1",
                            "suite_name": "core-v1",
                            "category": "api",
                            "dataset_version": "2026-11-v1",
                            "engine_version": "0.5.0",
                            "provider": "openai",
                            "model": "gpt-4o",
                            "optimization_mode": "balanced",
                            "sample_count": 4,
                            "unit_test_pass_rate": 1.0,
                            "constraint_preservation_rate": 1.0,
                            "identifier_preservation_rate": 1.0,
                            "median_reduction_pct": 15.09,
                            "p50_latency_ms": 7.7,
                            "p95_latency_ms": 9.7,
                            "negative_savings_count": 1,
                        }
                    ],
                },
                headers=auth_headers,
            )
            assert bench.status_code == 200

            # Query Analytics Overview -> exactly 3 unique runs (not 4 despite replay!)
            overview = client.get("/api/cloud/v1/analytics/overview", headers=auth_headers).json()
            assert overview["totals"]["total_runs"] == 3
            assert overview["accuracy_breakdown"]["exact_runs"] == 2
            assert overview["accuracy_breakdown"]["estimated_runs"] == 1
            assert overview["accuracy_breakdown"]["estimated_tokens_saved"] == 150
            assert overview["accuracy_breakdown"]["provider_confirmed_runs"] == 1
            assert overview["accuracy_breakdown"]["provider_confirmed_input_tokens"] == 345
            assert overview["accuracy_breakdown"]["provider_confirmed_tokens_saved"] == 150
            assert overview["cost_avoided"]["estimated_cost_avoided_usd"] == 0.00045
            assert overview["cost_avoided"]["provider_confirmed_cost_avoided_usd"] == 0.00045
            assert overview["validation"]["fallback_validation_failed"] == 1
            assert overview["validation"]["validated_runs"] == 2
            assert len(overview["benchmarks"]) == 1
            assert overview["latency"]["sample_count"] == 3
            assert overview["latency"]["p95_ms"] >= overview["latency"]["p50_ms"]

            # Test filters: provider=anthropic and granularity=weekly
            filtered = client.get(
                "/api/cloud/v1/analytics/overview?provider=anthropic&granularity=weekly",
                headers=auth_headers,
            ).json()
            assert filtered["totals"]["total_runs"] == 1
            assert filtered["granularity"] == "weekly"
            assert len(filtered["trends"]) == 1
            assert filtered["trends"][0]["bucket"].startswith("2026-W")
    finally:
        local_svc.close()
