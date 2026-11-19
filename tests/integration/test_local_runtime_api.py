"""Integration tests covering all 10 /api/v1 endpoints, SQLite metadata storage, OpenAPI parity, and availability."""

from __future__ import annotations

import sqlite3
from pathlib import Path

import yaml
from fastapi.testclient import TestClient

from project_t_local_runtime import LocalRuntimeService, RuntimeConfig, create_app

ROOT = Path(__file__).resolve().parents[2]
OPENAPI_YAML_PATH = ROOT / "packages" / "contracts" / "schemas" / "openapi-local-v1.yaml"


def _make_client(tmp_path: Path, workspace: Path | None = None) -> tuple[TestClient, dict[str, str], LocalRuntimeService]:
    workspaces = (workspace,) if workspace is not None else ()
    cfg = RuntimeConfig(
        data_dir=tmp_path / "runtime_data",
        use_os_keyring=False,
        approved_workspaces=workspaces,
        allowed_origins=("chrome-extension://testext123",),
    )
    service = LocalRuntimeService(config=cfg)
    app = create_app(service=service)
    client = TestClient(app)
    headers = {"Authorization": f"Bearer {service.credentials.bearer_token}"}
    return client, headers, service


def test_all_10_api_v1_endpoints_and_metadata_only_sqlite(tmp_path: Path) -> None:
    workspace = tmp_path / "sample_repo"
    (workspace / "src").mkdir(parents=True)
    (workspace / "tests").mkdir(parents=True)
    (workspace / "src" / "jwt_auth.py").write_text(
        "def verify_jwt_token(token: str) -> bool:\n    return bool(token)\n",
        encoding="utf-8",
    )
    (workspace / "tests" / "test_jwt_auth.py").write_text(
        "def test_verify_jwt_token():\n    assert True\n",
        encoding="utf-8",
    )
    (workspace / "README.md").write_text("# Sample Repo\nAuthentication notes.\n", encoding="utf-8")

    client, headers, service = _make_client(tmp_path, workspace=workspace)
    try:
        # 1. GET /api/v1/health (unauthenticated)
        health = client.get("/api/v1/health")
        assert health.status_code == 200
        assert health.json()["status"] == "ok"
        assert health.json()["engine_ready"] is True
        assert health.json()["sqlite_ready"] is True

        # 2. POST /api/v1/optimize
        secret_phrase = "SUPER_SECRET_USER_PROMPT_PAYLOAD_DO_NOT_STORE"
        opt_payload = {
            "content": (
                f"Hello, could you please inspect `{secret_phrase}` in order to verify `verify_jwt_token`?\n\n"
                "Repeated context block about JWT header validation and session routing.\n\n"
                "Repeated context block about JWT header validation and session routing.\n\n"
                "Do not change the database schema."
            ),
            "provider": "openai",
            "model": "gpt-4o",
            "mode": "balanced",
            "integration": "vscode",
        }
        opt_res = client.post("/api/v1/optimize", json=opt_payload, headers=headers)
        assert opt_res.status_code == 200
        opt_body = opt_res.json()
        assert opt_body["tokens"]["saved"] > 0
        assert opt_body["tokens"]["accuracy"] == "exact"
        assert opt_body["validation"]["passed"] is True
        assert opt_body["original_content"] == opt_payload["content"]
        assert "Do not change the database schema." in opt_body["optimized_content"]

        # Verify SQLite persisted metadata ONLY (zero raw prompt text stored anywhere in DB)
        conn = sqlite3.connect(service.config.resolved_db_path)
        runs = conn.execute("SELECT integration, status, content_type FROM optimization_runs").fetchall()
        assert len(runs) == 1
        assert runs[0] == ("vscode", "validated", "developer_prompt")
        db_dump = "\n".join(conn.iterdump())
        conn.close()
        assert secret_phrase not in db_dump

        # 3. POST /api/v1/count (plain text and structured request_payload)
        cnt_text = client.post(
            "/api/v1/count",
            json={"text": "Fix auth bug", "provider": "openai", "model": "gpt-4o"},
            headers=headers,
        )
        assert cnt_text.status_code == 200
        assert cnt_text.json()["accuracy"] == "exact"
        assert cnt_text.json()["count"] > 0

        cnt_req = client.post(
            "/api/v1/count",
            json={
                "request_payload": {
                    "system": "Be concise",
                    "messages": [{"role": "user", "content": "Hello"}],
                },
                "provider": "anthropic",
                "model": "claude-sonnet-4",
            },
            headers=headers,
        )
        assert cnt_req.status_code == 200
        assert cnt_req.json()["accuracy"] == "estimated"

        # 4. POST /api/v1/analyze
        an_res = client.post(
            "/api/v1/analyze",
            json={"content": "Fix verify_jwt_token in src/jwt_auth.py. Never drop schema.", "provider": "openai", "model": "gpt-4o"},
            headers=headers,
        )
        assert an_res.status_code == 200
        an_body = an_res.json()
        assert an_body["classification"]["mapped_content_type"] == "developer_prompt"
        assert "Never drop schema." in an_body["constraints"]["constraints"]
        assert any(s["value"] == "verify_jwt_token" for s in an_body["protected_spans"])

        # 5. POST /api/v1/context/select
        sel_res = client.post(
            "/api/v1/context/select",
            json={
                "task_description": "Fix verify_jwt_token verification",
                "workspace_root": str(workspace),
                "pinned_files": ["README.md"],
                "max_files": 5,
                "max_tokens": 2000,
            },
            headers=headers,
        )
        assert sel_res.status_code == 200
        sel_paths = [f["relative_path"] for f in sel_res.json()["selected_files"]]
        assert "README.md" in sel_paths
        assert "src/jwt_auth.py" in sel_paths
        assert "tests/test_jwt_auth.py" in sel_paths

        # 6. POST /api/v1/context/compress
        cc_res = client.post(
            "/api/v1/context/compress",
            json={
                "items": [
                    {"id": "a", "content": "Duplicate architectural constraint note for context compression.", "pinned": False},
                    {"id": "b", "content": "Duplicate architectural constraint note for context compression.", "pinned": True},
                ],
                "project_id": "proj_1",
            },
            headers=headers,
        )
        assert cc_res.status_code == 200
        assert cc_res.json()["tokens"]["saved"] > 0

        # 7. POST /api/v1/logs/compress
        noise = "\n".join(f"PASS tests/test_{i}.py" for i in range(25))
        log_res = client.post(
            "/api/v1/logs/compress",
            json={
                "command": "pytest",
                "exit_code": 1,
                "output": f"{noise}\nValueError: invalid jwt\nFAILED tests/test_jwt_auth.py\n1 failed, 25 passed",
            },
            headers=headers,
        )
        assert log_res.status_code == 200
        assert log_res.json()["tokens"]["saved"] > 0
        assert "ValueError: invalid jwt" in log_res.json()["optimized_content"]

        # 8. GET /api/v1/metrics
        met_res = client.get("/api/v1/metrics?window_days=30", headers=headers)
        assert met_res.status_code == 200
        assert met_res.json()["total_runs"] >= 3
        assert met_res.json()["total_tokens_saved"] > 0

        # 9. GET & PUT /api/v1/settings
        get_set = client.get("/api/v1/settings", headers=headers)
        assert get_set.status_code == 200
        assert get_set.json()["default_mode"] == "balanced"
        assert get_set.json()["cloud_sync_enabled"] is False

        put_set = client.put(
            "/api/v1/settings",
            json={"default_mode": "safe", "local_retention_days": 14},
            headers=headers,
        )
        assert put_set.status_code == 200
        assert put_set.json()["default_mode"] == "safe"
        assert put_set.json()["local_retention_days"] == 14

        # 10. GET /api/v1/providers
        prov_res = client.get("/api/v1/providers", headers=headers)
        assert prov_res.status_code == 200
        assert [p["id"] for p in prov_res.json()["providers"]] == [
            "local",
            "openai",
            "anthropic",
            "google",
        ]
    finally:
        service.close()


def test_fastapi_openapi_matches_canonical_openapi_spec(tmp_path: Path) -> None:
    client, _, service = _make_client(tmp_path)
    try:
        canonical = yaml.safe_load(OPENAPI_YAML_PATH.read_text(encoding="utf-8"))
        generated = client.app.openapi()

        expected_paths = {f"/api/v1{p}" for p in canonical["paths"].keys()}
        assert set(generated["paths"].keys()) == expected_paths

        for raw_path, methods in canonical["paths"].items():
            full_path = f"/api/v1{raw_path}"
            for method in methods.keys():
                assert method in generated["paths"][full_path], (
                    f"Missing method {method.upper()} {full_path} in FastAPI OpenAPI"
                )
    finally:
        service.close()


def test_controlled_availability_soak_meets_99_percent_target(tmp_path: Path) -> None:
    client, headers, service = _make_client(tmp_path)
    try:
        total = 100
        ok_count = 0
        for i in range(total):
            r1 = client.get("/api/v1/health")
            r2 = client.post(
                "/api/v1/optimize",
                json={"content": f"Please fix bug #{i} in order to deploy cleanly."},
                headers=headers,
            )
            if r1.status_code == 200 and r2.status_code == 200:
                ok_count += 1
        assert (ok_count / total) >= 0.99
    finally:
        service.close()
