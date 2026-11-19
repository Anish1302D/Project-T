"""Security and privacy boundary tests for Local Runtime."""

from __future__ import annotations

import logging
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from project_t_local_runtime import CredentialStore, LocalRuntimeService, RuntimeConfig, create_app


def _make_sec_client(
    tmp_path: Path,
    *,
    max_body_bytes: int = 2_097_152,
    rate_limit_requests: int = 120,
    allowed_origins: tuple[str, ...] = ("chrome-extension://allowed123",),
    approved_workspaces: tuple[Path, ...] = (),
) -> tuple[TestClient, dict[str, str], LocalRuntimeService]:
    cfg = RuntimeConfig(
        data_dir=tmp_path / "sec_data",
        use_os_keyring=False,
        max_body_bytes=max_body_bytes,
        rate_limit_requests=rate_limit_requests,
        rate_limit_window_seconds=60,
        allowed_origins=allowed_origins,
        approved_workspaces=approved_workspaces,
    )
    service = LocalRuntimeService(config=cfg)
    client = TestClient(create_app(service=service))
    headers = {"Authorization": f"Bearer {service.credentials.bearer_token}"}
    return client, headers, service


def test_refuses_public_bind_and_wildcard_cors_by_default() -> None:
    with pytest.raises(ValueError, match="non-loopback"):
        RuntimeConfig(host="0.0.0.0")

    with pytest.raises(ValueError, match="Wildcard"):
        RuntimeConfig(allowed_origins=("*",))


def test_bearer_authentication_enforced_and_token_rotation_invalidates_old_token(tmp_path: Path) -> None:
    client, headers, service = _make_sec_client(tmp_path)
    try:
        # Missing token -> 401
        res_missing = client.post("/api/v1/optimize", json={"content": "hello"})
        assert res_missing.status_code == 401
        assert res_missing.json()["error"]["code"] == "unauthorized"

        # Wrong token -> 401
        res_bad = client.post(
            "/api/v1/optimize",
            json={"content": "hello"},
            headers={"Authorization": "Bearer wrong-token"},
        )
        assert res_bad.status_code == 401

        # Valid token succeeds
        assert client.get("/api/v1/settings", headers=headers).status_code == 200

        # Rotate token -> old token rejected, new token accepted
        old_token = service.credentials.bearer_token
        rotated = CredentialStore(service.config.data_dir, use_os_keyring=False).rotate_token()
        assert rotated.bearer_token != old_token
        service.credentials = rotated

        assert client.get("/api/v1/settings", headers=headers).status_code == 401
        assert (
            client.get(
                "/api/v1/settings",
                headers={"Authorization": f"Bearer {rotated.bearer_token}"},
            ).status_code
            == 200
        )
    finally:
        service.close()


def test_blocks_dns_rebinding_host_and_disallowed_origin_cors(tmp_path: Path) -> None:
    client, headers, service = _make_sec_client(tmp_path)
    try:
        # Disallowed Host header -> 403
        bad_host = client.get("/api/v1/health", headers={"Host": "evil.attacker.com"})
        assert bad_host.status_code == 403
        assert bad_host.json()["error"]["code"] == "forbidden_origin"

        # Disallowed Origin header -> 403
        bad_origin = client.post(
            "/api/v1/optimize",
            json={"content": "hello"},
            headers={**headers, "Origin": "https://evil.example.com"},
        )
        assert bad_origin.status_code == 403
        assert bad_origin.json()["error"]["code"] == "forbidden_origin"

        # Allowlisted Origin echoes exact origin (never '*')
        good_origin = client.post(
            "/api/v1/optimize",
            json={"content": "hello"},
            headers={**headers, "Origin": "chrome-extension://allowed123"},
        )
        assert good_origin.status_code == 200
        assert good_origin.headers.get("access-control-allow-origin") == "chrome-extension://allowed123"
    finally:
        service.close()


def test_blocks_unapproved_workspace_and_path_traversal(tmp_path: Path) -> None:
    approved = tmp_path / "approved_ws"
    outside = tmp_path / "outside_secret"
    approved.mkdir()
    outside.mkdir()
    (approved / "main.py").write_text("print('ok')\n", encoding="utf-8")
    (outside / "secret.txt").write_text("SECRET_KEY=12345\n", encoding="utf-8")

    client, headers, service = _make_sec_client(tmp_path, approved_workspaces=(approved,))
    try:
        unapproved_res = client.post(
            "/api/v1/context/select",
            json={"task_description": "secret", "workspace_root": str(outside)},
            headers=headers,
        )
        assert unapproved_res.status_code == 403
        assert unapproved_res.json()["error"]["code"] == "forbidden_workspace"

        traversal_res = client.post(
            "/api/v1/context/select",
            json={
                "task_description": "secret",
                "workspace_root": str(approved),
                "pinned_files": ["../outside_secret/secret.txt"],
            },
            headers=headers,
        )
        assert traversal_res.status_code == 403
        assert traversal_res.json()["error"]["code"] == "forbidden_workspace"
    finally:
        service.close()


def test_enforces_payload_size_limit(tmp_path: Path) -> None:
    client, headers, service = _make_sec_client(
        tmp_path,
        max_body_bytes=256,
    )
    try:
        too_big = client.post(
            "/api/v1/optimize",
            json={"content": "A" * 500},
            headers=headers,
        )
        assert too_big.status_code == 413
        assert too_big.json()["error"]["code"] == "payload_too_large"
    finally:
        service.close()


def test_enforces_rate_limit(tmp_path: Path) -> None:
    client, headers, service = _make_sec_client(
        tmp_path,
        rate_limit_requests=2,
    )
    try:
        r1 = client.get("/api/v1/settings", headers=headers)
        r2 = client.get("/api/v1/settings", headers=headers)
        r3 = client.get("/api/v1/settings", headers=headers)
        assert r1.status_code == 200
        assert r2.status_code == 200
        assert r3.status_code == 429
        assert r3.json()["error"]["code"] == "rate_limit_exceeded"
    finally:
        service.close()


def test_validation_errors_never_echo_raw_content_or_secrets(
    tmp_path: Path, caplog: pytest.LogCaptureFixture
) -> None:
    client, headers, service = _make_sec_client(tmp_path)
    try:
        secret_input = "sk-mysecretkey99999999"
        with caplog.at_level(logging.DEBUG):
            bad_req = client.post(
                "/api/v1/optimize",
                json={"content": secret_input, "unexpected_field": "Bearer leaked_token_xyz"},
                headers=headers,
            )
        assert bad_req.status_code == 422
        body_text = bad_req.text
        assert secret_input not in body_text
        assert "leaked_token_xyz" not in body_text
        assert service.credentials.bearer_token not in body_text
        assert secret_input not in caplog.text
        assert service.credentials.bearer_token not in caplog.text
    finally:
        service.close()
