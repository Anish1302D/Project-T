"""Security and privacy boundary tests for optional cloud sync, offline mode, and DDL scope."""

from __future__ import annotations

import logging
from pathlib import Path

import pytest
import yaml
from fastapi.testclient import TestClient

from project_t_cloud_services import CloudConfig, create_control_plane_app
from project_t_cloud_services.authentication import hash_password, verify_password
from project_t_cloud_services.cloud_sync import (
    SyncBoundaryViolationError,
    validate_no_sensitive_sync_data,
)
from project_t_contracts import OptimizationMode, OptimizationRequestWire
from project_t_local_runtime import LocalRuntimeService, RuntimeConfig

ROOT = Path(__file__).resolve().parents[2]


def test_local_runtime_works_offline_and_default_sync_is_disabled(tmp_path: Path) -> None:
    svc = LocalRuntimeService(
        config=RuntimeConfig(
            data_dir=tmp_path,
            db_path=tmp_path / "offline_local.db",
            use_os_keyring=False,
            allow_tiktoken=True,
        )
    )
    try:
        res = svc.optimize(
            OptimizationRequestWire(
                content=(
                    "Hello, could you please help check `verifyJwtToken` in auth.py?\n\n"
                    "Rule: Keep HTTP 401 behavior.\n\nRule: Keep HTTP 401 behavior."
                ),
                provider="openai",
                model="gpt-4o",
                mode=OptimizationMode.BALANCED,
                integration="vscode",
            )
        )
        assert res.tokens.original > res.tokens.optimized
        assert "verifyJwtToken" in res.optimized_content

        # Default opt-in disabled: never attempts network call
        default_res = svc.sync_metadata_to_cloud(
            cloud_base_url="http://127.0.0.1:59999",
            sync_token="unused",
            opt_in=False,
        )
        assert default_res["synced"] is False
        assert default_res["reason"] == "sync_disabled_or_unconfigured"

        # Opt-in with unreachable cloud fails gracefully without disturbing local runtime
        unreachable_res = svc.sync_metadata_to_cloud(
            cloud_base_url="http://127.0.0.1:59999",
            sync_token="token-abc",
            opt_in=True,
        )
        assert unreachable_res["synced"] is False
        assert unreachable_res["reason"] == "cloud_unreachable"

        # Exported payload must strictly contain metadata only
        exported = svc.build_metadata_sync_payload()
        validate_no_sensitive_sync_data(exported)
        serialized = str(exported)
        assert "verifyJwtToken" not in serialized
        assert "auth.py" not in serialized
        assert "Hello, could you please" not in serialized
    finally:
        svc.close()


@pytest.mark.parametrize(
    "bad_payload",
    [
        {"installation_id": "inst_1", "raw_content": "secret prompt text"},
        {"installation_id": "inst_1", "runs": [{"run_id": "r1", "original_content": "secret"}]},
        {"installation_id": "inst_1", "runs": [{"run_id": "r1", "source_code": "def foo(): pass"}]},
        {"installation_id": "inst_1", "runs": [{"run_id": "r1", "file_path": "/src/secret.py"}]},
        {"installation_id": "inst_1", "runs": [{"run_id": "r1", "block_hash": "abc123"}]},
        {"installation_id": "inst_1", "runs": [{"run_id": "r1", "simhash_64": "0011ff"}]},
        {"installation_id": "inst_1", "runs": [{"run_id": "r1", "warnings": ["sk-secretkey12345678"]}]},
        {"installation_id": "inst_1", "runs": [{"run_id": "r1", "warnings": ["C:\\Users\\alice\\repo\\a.py"]}]},
    ],
)
def test_cloud_sync_boundary_validator_and_api_reject_sensitive_data(
    tmp_path: Path, bad_payload: dict
) -> None:
    with pytest.raises(SyncBoundaryViolationError):
        validate_no_sensitive_sync_data(bad_payload)

    app = create_control_plane_app(
        CloudConfig(data_dir=tmp_path, database_url=f"sqlite:///{tmp_path / 'cloud.db'}")
    )
    with TestClient(app) as client:
        reg = client.post(
            "/api/cloud/v1/auth/register",
            json={"email": "sec@example.com", "display_name": "Sec", "password": "strong-password-1"},
        ).json()
        token = reg["access_token"]
        client.post(
            "/api/cloud/v1/auth/devices/pair",
            json={
                "installation_id": "inst_1",
                "device_label": "SecBox",
                "os_platform": "Linux",
                "sync_enabled": True,
            },
            headers={"Authorization": f"Bearer {token}"},
        )
        resp = client.post(
            "/api/cloud/v1/sync/runs",
            json=bad_payload,
            headers={"Authorization": f"Bearer {token}"},
        )
        assert resp.status_code == 422
        assert resp.json()["error"]["code"] == "sync_boundary_violation"


def test_cross_tenant_and_disabled_sync_rejected_with_403(tmp_path: Path) -> None:
    app = create_control_plane_app(
        CloudConfig(data_dir=tmp_path, database_url=f"sqlite:///{tmp_path / 'cloud.db'}")
    )
    with TestClient(app) as client:
        u1 = client.post(
            "/api/cloud/v1/auth/register",
            json={"email": "u1@example.com", "display_name": "U1", "password": "password-one-123"},
        ).json()["access_token"]
        u2 = client.post(
            "/api/cloud/v1/auth/register",
            json={"email": "u2@example.com", "display_name": "U2", "password": "password-two-123"},
        ).json()["access_token"]

        # U1 pairs with sync_enabled=False
        client.post(
            "/api/cloud/v1/auth/devices/pair",
            json={
                "installation_id": "inst_disabled",
                "device_label": "DisabledBox",
                "os_platform": "Windows",
                "sync_enabled": False,
            },
            headers={"Authorization": f"Bearer {u1}"},
        )
        r_disabled = client.post(
            "/api/cloud/v1/sync/runs",
            json={"installation_id": "inst_disabled", "runs": []},
            headers={"Authorization": f"Bearer {u1}"},
        )
        assert r_disabled.status_code == 403
        assert r_disabled.json()["error"]["code"] == "sync_disabled"

        # U2 cannot sync to U1's installation even after enabling
        client.post(
            "/api/cloud/v1/auth/devices/pair",
            json={
                "installation_id": "inst_enabled",
                "device_label": "EnabledBox",
                "os_platform": "Windows",
                "sync_enabled": True,
            },
            headers={"Authorization": f"Bearer {u1}"},
        )
        r_cross = client.post(
            "/api/cloud/v1/sync/runs",
            json={"installation_id": "inst_enabled", "runs": []},
            headers={"Authorization": f"Bearer {u2}"},
        )
        assert r_cross.status_code == 403


def test_pbkdf2_password_hashing_and_cloud_ddl_boundary() -> None:
    h1 = hash_password("correct-horse-battery-staple")
    h2 = hash_password("correct-horse-battery-staple")
    assert h1 != h2  # unique CSPRNG salt
    assert verify_password("correct-horse-battery-staple", h1) is True
    assert verify_password("wrong-password", h1) is False

    pg_sql = (
        ROOT / "infrastructure" / "database" / "postgres" / "001_initial_cloud_schema.sql"
    ).read_text(encoding="utf-8")
    for expected_table in (
        "users",
        "devices",
        "installations",
        "providers",
        "models",
        "optimization_rules",
        "optimization_runs",
        "token_metrics",
        "cost_metrics",
        "benchmark_results",
    ):
        assert f"CREATE TABLE IF NOT EXISTS {expected_table}" in pg_sql

    # Strip SQL comment lines before verifying omitted local/deferred features in active DDL
    pg_ddl_statements = "\n".join(
        line for line in pg_sql.splitlines() if not line.strip().startswith("--")
    )
    assert "CREATE TABLE IF NOT EXISTS project_profiles" not in pg_ddl_statements
    assert "CREATE TABLE IF NOT EXISTS context_fingerprints" not in pg_ddl_statements
    assert "fts5" not in pg_ddl_statements.lower()
    assert "pgvector" not in pg_ddl_statements.lower()

    compose = yaml.safe_load((ROOT / "docker-compose.yml").read_text(encoding="utf-8"))
    assert set(compose["services"].keys()) == {"postgres", "redis", "control-plane", "dashboard"}
