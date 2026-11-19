"""Dual-engine cloud database store (PostgreSQL for Docker/cloud, SQLite fallback for offline tests)."""

from __future__ import annotations

import json
import sqlite3
import threading
import uuid
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from project_t_provider_adapters import ProviderRegistry

_POSTGRES_SCHEMA_PATH = (
    Path(__file__).resolve().parents[3]
    / "infrastructure"
    / "database"
    / "postgres"
    / "001_initial_cloud_schema.sql"
)

_SQLITE_CLOUD_DDL = """
PRAGMA foreign_keys = ON;

CREATE TABLE IF NOT EXISTS users (
    id TEXT PRIMARY KEY,
    email TEXT NOT NULL UNIQUE,
    display_name TEXT NOT NULL,
    password_hash TEXT NOT NULL,
    created_at TEXT NOT NULL DEFAULT (CURRENT_TIMESTAMP),
    updated_at TEXT NOT NULL DEFAULT (CURRENT_TIMESTAMP)
);

CREATE TABLE IF NOT EXISTS devices (
    id TEXT PRIMARY KEY,
    user_id TEXT NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    device_label TEXT NOT NULL,
    os_platform TEXT NOT NULL,
    created_at TEXT NOT NULL DEFAULT (CURRENT_TIMESTAMP),
    last_seen_at TEXT
);

CREATE TABLE IF NOT EXISTS installations (
    id TEXT PRIMARY KEY,
    device_id TEXT REFERENCES devices(id) ON DELETE SET NULL,
    user_id TEXT REFERENCES users(id) ON DELETE SET NULL,
    runtime_version TEXT NOT NULL,
    schema_version TEXT NOT NULL DEFAULT '1.0',
    sync_enabled INTEGER NOT NULL DEFAULT 0 CHECK (sync_enabled IN (0, 1)),
    created_at TEXT NOT NULL DEFAULT (CURRENT_TIMESTAMP),
    last_active_at TEXT
);

CREATE TABLE IF NOT EXISTS providers (
    id TEXT PRIMARY KEY,
    display_name TEXT NOT NULL,
    tokenizer_family TEXT NOT NULL,
    is_enabled INTEGER NOT NULL DEFAULT 1 CHECK (is_enabled IN (0, 1)),
    metadata_json TEXT NOT NULL DEFAULT '{}',
    updated_at TEXT NOT NULL DEFAULT (CURRENT_TIMESTAMP)
);

CREATE TABLE IF NOT EXISTS models (
    id TEXT PRIMARY KEY,
    provider_id TEXT NOT NULL REFERENCES providers(id) ON DELETE CASCADE,
    model_name TEXT NOT NULL,
    tokenizer_name TEXT NOT NULL,
    context_window INTEGER,
    supports_exact_count INTEGER NOT NULL DEFAULT 0 CHECK (supports_exact_count IN (0, 1)),
    pricing_version TEXT NOT NULL,
    input_cost_per_1m_usd REAL,
    cached_input_cost_per_1m_usd REAL,
    output_cost_per_1m_usd REAL,
    updated_at TEXT NOT NULL DEFAULT (CURRENT_TIMESTAMP),
    UNIQUE (provider_id, model_name)
);

CREATE TABLE IF NOT EXISTS optimization_rules (
    id TEXT PRIMARY KEY,
    installation_id TEXT NOT NULL REFERENCES installations(id) ON DELETE CASCADE,
    project_id TEXT,
    scope TEXT NOT NULL CHECK (scope IN ('global', 'integration', 'project')),
    mode TEXT NOT NULL DEFAULT 'balanced' CHECK (mode IN ('safe', 'balanced', 'aggressive')),
    preserve_identifiers INTEGER NOT NULL DEFAULT 1 CHECK (preserve_identifiers IN (0, 1)),
    allow_ai_semantic_compression INTEGER NOT NULL DEFAULT 0 CHECK (allow_ai_semantic_compression IN (0, 1)),
    min_meaningful_savings_tokens INTEGER NOT NULL DEFAULT 10,
    rules_json TEXT NOT NULL DEFAULT '{}',
    version INTEGER NOT NULL DEFAULT 1,
    updated_at TEXT NOT NULL DEFAULT (CURRENT_TIMESTAMP)
);

CREATE TABLE IF NOT EXISTS optimization_runs (
    id TEXT PRIMARY KEY,
    run_id TEXT NOT NULL,
    request_id TEXT NOT NULL,
    installation_id TEXT NOT NULL REFERENCES installations(id) ON DELETE CASCADE,
    device_id TEXT REFERENCES devices(id) ON DELETE SET NULL,
    provider_id TEXT REFERENCES providers(id) ON DELETE SET NULL,
    model_id TEXT REFERENCES models(id) ON DELETE SET NULL,
    model_name TEXT NOT NULL,
    integration TEXT NOT NULL CHECK (integration IN ('vscode', 'browser', 'mcp', 'gateway', 'cli', 'api')),
    content_type TEXT NOT NULL CHECK (
        content_type IN (
            'prompt',
            'developer_prompt',
            'source_code',
            'json',
            'documentation',
            'terminal_output',
            'conversation',
            'tool_result'
        )
    ),
    optimization_mode TEXT NOT NULL CHECK (optimization_mode IN ('safe', 'balanced', 'aggressive')),
    status TEXT NOT NULL CHECK (status IN ('validated', 'fallback_validation_failed', 'fallback_no_savings', 'fallback_error')),
    methods_json TEXT NOT NULL DEFAULT '[]',
    warnings_json TEXT NOT NULL DEFAULT '[]',
    quality_score REAL,
    duration_ms INTEGER NOT NULL DEFAULT 0,
    created_at TEXT NOT NULL DEFAULT (CURRENT_TIMESTAMP),
    UNIQUE (installation_id, run_id)
);

CREATE TABLE IF NOT EXISTS token_metrics (
    id TEXT PRIMARY KEY,
    run_id TEXT NOT NULL UNIQUE REFERENCES optimization_runs(id) ON DELETE CASCADE,
    original_tokens INTEGER NOT NULL CHECK (original_tokens >= 0),
    optimized_tokens INTEGER NOT NULL CHECK (optimized_tokens >= 0),
    tokens_saved INTEGER NOT NULL,
    reduction_percentage REAL NOT NULL,
    accuracy TEXT NOT NULL CHECK (accuracy IN ('exact', 'estimated')),
    provider_confirmed_original_tokens INTEGER,
    provider_confirmed_input_tokens INTEGER,
    created_at TEXT NOT NULL DEFAULT (CURRENT_TIMESTAMP)
);

CREATE TABLE IF NOT EXISTS cost_metrics (
    id TEXT PRIMARY KEY,
    run_id TEXT NOT NULL UNIQUE REFERENCES optimization_runs(id) ON DELETE CASCADE,
    pricing_version TEXT NOT NULL,
    estimated_cost_avoided_usd REAL NOT NULL DEFAULT 0.0,
    provider_confirmed_cost_avoided_usd REAL,
    currency TEXT NOT NULL DEFAULT 'USD',
    created_at TEXT NOT NULL DEFAULT (CURRENT_TIMESTAMP)
);

CREATE TABLE IF NOT EXISTS benchmark_results (
    id TEXT PRIMARY KEY,
    suite_name TEXT NOT NULL,
    category TEXT NOT NULL CHECK (
        category IN (
            'prompt',
            'constraint',
            'code',
            'repository',
            'log',
            'conversation',
            'api',
            'latency'
        )
    ),
    dataset_version TEXT NOT NULL,
    engine_version TEXT NOT NULL,
    model_id TEXT REFERENCES models(id) ON DELETE SET NULL,
    model_name TEXT NOT NULL DEFAULT 'gpt-4o',
    optimization_mode TEXT NOT NULL CHECK (optimization_mode IN ('safe', 'balanced', 'aggressive')),
    sample_count INTEGER NOT NULL CHECK (sample_count >= 0),
    unit_test_pass_rate REAL,
    constraint_preservation_rate REAL,
    identifier_preservation_rate REAL,
    median_reduction_pct REAL,
    p50_latency_ms REAL,
    p95_latency_ms REAL,
    negative_savings_count INTEGER NOT NULL DEFAULT 0,
    paired_quality_delta REAL,
    report_uri TEXT,
    executed_at TEXT NOT NULL DEFAULT (CURRENT_TIMESTAMP)
);
"""


def _parse_json_field(val: Any, default: Any) -> Any:
    if val is None:
        return default
    if isinstance(val, (dict, list)):
        return val
    try:
        return json.loads(str(val))
    except Exception:
        return default


def _to_iso_str(val: Any) -> str:
    if isinstance(val, datetime):
        if val.tzinfo is None:
            return val.replace(tzinfo=UTC).isoformat()
        return val.astimezone(UTC).isoformat()
    return str(val)


class CloudDatabase:
    """Thread-safe metadata-only persistence layer over PostgreSQL or SQLite."""

    def __init__(
        self,
        *,
        database_url: str | None = None,
        sqlite_path: Path | str | None = None,
        postgres_schema_path: Path = _POSTGRES_SCHEMA_PATH,
    ) -> None:
        self._database_url = database_url
        self._is_pg = bool(
            database_url and database_url.strip().lower().startswith(("postgresql://", "postgres://"))
        )
        self._lock = threading.RLock()
        self._postgres_schema_path = postgres_schema_path

        if self._is_pg:
            import psycopg
            from psycopg.rows import dict_row

            assert database_url is not None
            self._conn = psycopg.connect(database_url, row_factory=dict_row, autocommit=False)
        else:
            target = str(sqlite_path or ":memory:")
            if target != ":memory:":
                Path(target).parent.mkdir(parents=True, exist_ok=True)
            self._conn = sqlite3.connect(target, check_same_thread=False)
            self._conn.row_factory = sqlite3.Row
            with self._lock:
                self._conn.execute("PRAGMA foreign_keys = ON;")
                if target != ":memory:":
                    self._conn.execute("PRAGMA journal_mode = WAL;")

    @property
    def backend_name(self) -> str:
        return "postgresql" if self._is_pg else "sqlite"

    def _q(self, query: str) -> str:
        return query.replace("?", "%s") if self._is_pg else query

    def _fetchall(self, query: str, params: tuple[Any, ...] = ()) -> list[dict[str, Any]]:
        with self._lock:
            cur = self._conn.execute(self._q(query), params)
            rows = cur.fetchall()
            return [dict(r) for r in rows]

    def _fetchone(self, query: str, params: tuple[Any, ...] = ()) -> dict[str, Any] | None:
        with self._lock:
            cur = self._conn.execute(self._q(query), params)
            row = cur.fetchone()
            return dict(row) if row is not None else None

    def _execute(self, query: str, params: tuple[Any, ...] = ()) -> None:
        with self._lock:
            self._conn.execute(self._q(query), params)

    def initialize(self, registry: ProviderRegistry) -> None:
        with self._lock:
            if self._is_pg:
                ddl = self._postgres_schema_path.read_text(encoding="utf-8")
                with self._conn.cursor() as cur:
                    cur.execute(ddl)
            else:
                self._conn.executescript(_SQLITE_CLOUD_DDL)
                self._conn.execute("PRAGMA foreign_keys = ON;")

            for provider in registry.list_catalog_entries():
                if self._is_pg:
                    self._execute(
                        """
                        INSERT INTO providers (id, display_name, tokenizer_family, is_enabled)
                        VALUES (?, ?, ?, TRUE)
                        ON CONFLICT (id) DO UPDATE SET
                            display_name = EXCLUDED.display_name,
                            updated_at = NOW()
                        """,
                        (provider.id, provider.display_name, provider.id),
                    )
                else:
                    self._execute(
                        """
                        INSERT OR IGNORE INTO providers (id, display_name, tokenizer_family, is_enabled)
                        VALUES (?, ?, ?, 1)
                        """,
                        (provider.id, provider.display_name, provider.id),
                    )
                for model in provider.models:
                    model_pk = f"{provider.id}:{model.model_name}"
                    if self._is_pg:
                        self._execute(
                            """
                            INSERT INTO models (
                                id, provider_id, model_name, tokenizer_name,
                                supports_exact_count, pricing_version
                            )
                            VALUES (?, ?, ?, ?, ?, ?)
                            ON CONFLICT (id) DO NOTHING
                            """,
                            (
                                model_pk,
                                provider.id,
                                model.model_name,
                                model.model_name,
                                model.supports_exact_local_count,
                                model.pricing_version,
                            ),
                        )
                    else:
                        self._execute(
                            """
                            INSERT OR IGNORE INTO models (
                                id, provider_id, model_name, tokenizer_name,
                                supports_exact_count, pricing_version
                            )
                            VALUES (?, ?, ?, ?, ?, ?)
                            """,
                            (
                                model_pk,
                                provider.id,
                                model.model_name,
                                model.model_name,
                                1 if model.supports_exact_local_count else 0,
                                model.pricing_version,
                            ),
                        )
            self._conn.commit()

    def is_ready(self) -> bool:
        try:
            row = self._fetchone("SELECT 1 AS ok")
            return row is not None
        except Exception:
            return False

    def create_user(self, *, email: str, display_name: str, password_hash: str) -> dict[str, Any]:
        user_id = f"usr_{uuid.uuid4().hex[:16]}"
        norm_email = email.strip().lower()
        with self._lock:
            self._execute(
                """
                INSERT INTO users (id, email, display_name, password_hash)
                VALUES (?, ?, ?, ?)
                """,
                (user_id, norm_email, display_name.strip(), password_hash),
            )
            self._conn.commit()
        user = self.get_user_by_id(user_id)
        assert user is not None
        return user

    def get_user_by_email(self, email: str) -> dict[str, Any] | None:
        return self._fetchone("SELECT * FROM users WHERE email = ?", (email.strip().lower(),))

    def get_user_by_id(self, user_id: str) -> dict[str, Any] | None:
        return self._fetchone("SELECT * FROM users WHERE id = ?", (user_id,))

    def pair_device_and_installation(
        self,
        *,
        user_id: str,
        device_id: str,
        device_label: str,
        os_platform: str,
        installation_id: str,
        runtime_version: str,
        sync_enabled: bool = True,
    ) -> tuple[dict[str, Any], dict[str, Any]]:
        now_val = datetime.now(tz=UTC) if self._is_pg else datetime.now(tz=UTC).strftime("%Y-%m-%d %H:%M:%S")
        sync_val: Any = sync_enabled if self._is_pg else (1 if sync_enabled else 0)
        with self._lock:
            self._execute(
                """
                INSERT INTO devices (id, user_id, device_label, os_platform, last_seen_at)
                VALUES (?, ?, ?, ?, ?)
                ON CONFLICT(id) DO UPDATE SET
                    user_id = excluded.user_id,
                    device_label = excluded.device_label,
                    os_platform = excluded.os_platform,
                    last_seen_at = excluded.last_seen_at
                """.replace("excluded.", "EXCLUDED." if self._is_pg else "excluded."),
                (device_id, user_id, device_label.strip(), os_platform.strip(), now_val),
            )
            self._execute(
                """
                INSERT INTO installations (id, device_id, user_id, runtime_version, sync_enabled, last_active_at)
                VALUES (?, ?, ?, ?, ?, ?)
                ON CONFLICT(id) DO UPDATE SET
                    device_id = excluded.device_id,
                    user_id = excluded.user_id,
                    runtime_version = excluded.runtime_version,
                    sync_enabled = excluded.sync_enabled,
                    last_active_at = excluded.last_active_at
                """.replace("excluded.", "EXCLUDED." if self._is_pg else "excluded."),
                (installation_id, device_id, user_id, runtime_version.strip(), sync_val, now_val),
            )
            self._conn.commit()
        dev = self._fetchone("SELECT * FROM devices WHERE id = ?", (device_id,))
        inst = self._fetchone("SELECT * FROM installations WHERE id = ?", (installation_id,))
        assert dev is not None and inst is not None
        return dev, inst

    def list_devices_for_user(self, user_id: str) -> list[dict[str, Any]]:
        rows = self._fetchall(
            """
            SELECT
                d.id AS device_id,
                d.device_label,
                d.os_platform,
                d.last_seen_at,
                i.id AS installation_id,
                i.runtime_version,
                i.sync_enabled,
                i.last_active_at
            FROM devices d
            LEFT JOIN installations i ON i.device_id = d.id
            WHERE d.user_id = ?
            ORDER BY d.created_at DESC
            """,
            (user_id,),
        )
        return [
            {
                "device_id": r["device_id"],
                "device_label": r["device_label"],
                "os_platform": r["os_platform"],
                "installation_id": r["installation_id"],
                "runtime_version": r["runtime_version"],
                "sync_enabled": bool(r["sync_enabled"]),
                "last_active_at": _to_iso_str(r["last_active_at"]) if r["last_active_at"] else None,
            }
            for r in rows
        ]

    def get_installation(self, installation_id: str) -> dict[str, Any] | None:
        return self._fetchone("SELECT * FROM installations WHERE id = ?", (installation_id,))

    def upsert_synced_runs(
        self,
        *,
        installation_id: str,
        device_id: str | None,
        runs: list[dict[str, Any]],
    ) -> tuple[int, int]:
        """Idempotent (installation_id, run_id) upsert into cloud runs, token_metrics, cost_metrics."""
        inserted_or_updated = 0
        now_fallback = datetime.now(tz=UTC) if self._is_pg else datetime.now(tz=UTC).strftime("%Y-%m-%d %H:%M:%S")
        excluded_kw = "EXCLUDED" if self._is_pg else "excluded"

        with self._lock:
            for run in runs:
                run_id = str(run["run_id"])
                run_pk = f"{installation_id}:{run_id}"
                provider = str(run["provider"]).strip().lower()
                model_name = str(run["model"]).strip()
                model_pk = f"{provider}:{model_name}"

                prov_row = self._fetchone("SELECT id FROM providers WHERE id = ?", (provider,))
                model_row = self._fetchone("SELECT id FROM models WHERE id = ?", (model_pk,))
                created_at_val = run.get("created_at") or now_fallback
                methods_raw = json.dumps(run.get("methods", []))
                warnings_raw = json.dumps(run.get("warnings", []))

                if self._is_pg:
                    self._execute(
                        f"""
                        INSERT INTO optimization_runs (
                            id, run_id, request_id, installation_id, device_id,
                            provider_id, model_id, model_name, integration, content_type,
                            optimization_mode, status, methods_json, warnings_json,
                            quality_score, duration_ms, created_at
                        )
                        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?::jsonb, ?::jsonb, ?, ?, ?)
                        ON CONFLICT (installation_id, run_id) DO UPDATE SET
                            request_id = {excluded_kw}.request_id,
                            device_id = {excluded_kw}.device_id,
                            provider_id = {excluded_kw}.provider_id,
                            model_id = {excluded_kw}.model_id,
                            model_name = {excluded_kw}.model_name,
                            integration = {excluded_kw}.integration,
                            content_type = {excluded_kw}.content_type,
                            optimization_mode = {excluded_kw}.optimization_mode,
                            status = {excluded_kw}.status,
                            methods_json = {excluded_kw}.methods_json,
                            warnings_json = {excluded_kw}.warnings_json,
                            quality_score = {excluded_kw}.quality_score,
                            duration_ms = {excluded_kw}.duration_ms
                        """,
                        (
                            run_pk,
                            run_id,
                            run["request_id"],
                            installation_id,
                            device_id,
                            prov_row["id"] if prov_row else None,
                            model_row["id"] if model_row else None,
                            model_name,
                            str(run["integration"]),
                            str(run["content_type"]),
                            str(run["optimization_mode"]),
                            str(run["status"]),
                            methods_raw,
                            warnings_raw,
                            run.get("quality_score"),
                            int(run["duration_ms"]),
                            created_at_val,
                        ),
                    )
                else:
                    self._execute(
                        f"""
                        INSERT INTO optimization_runs (
                            id, run_id, request_id, installation_id, device_id,
                            provider_id, model_id, model_name, integration, content_type,
                            optimization_mode, status, methods_json, warnings_json,
                            quality_score, duration_ms, created_at
                        )
                        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                        ON CONFLICT (installation_id, run_id) DO UPDATE SET
                            request_id = {excluded_kw}.request_id,
                            device_id = {excluded_kw}.device_id,
                            provider_id = {excluded_kw}.provider_id,
                            model_id = {excluded_kw}.model_id,
                            model_name = {excluded_kw}.model_name,
                            integration = {excluded_kw}.integration,
                            content_type = {excluded_kw}.content_type,
                            optimization_mode = {excluded_kw}.optimization_mode,
                            status = {excluded_kw}.status,
                            methods_json = {excluded_kw}.methods_json,
                            warnings_json = {excluded_kw}.warnings_json,
                            quality_score = {excluded_kw}.quality_score,
                            duration_ms = {excluded_kw}.duration_ms
                        """,
                        (
                            run_pk,
                            run_id,
                            run["request_id"],
                            installation_id,
                            device_id,
                            prov_row["id"] if prov_row else None,
                            model_row["id"] if model_row else None,
                            model_name,
                            str(run["integration"]),
                            str(run["content_type"]),
                            str(run["optimization_mode"]),
                            str(run["status"]),
                            methods_raw,
                            warnings_raw,
                            run.get("quality_score"),
                            int(run["duration_ms"]),
                            created_at_val,
                        ),
                    )

                tok_pk = f"tok_{run_pk}"
                self._execute(
                    f"""
                    INSERT INTO token_metrics (
                        id, run_id, original_tokens, optimized_tokens, tokens_saved,
                        reduction_percentage, accuracy,
                        provider_confirmed_original_tokens, provider_confirmed_input_tokens
                    )
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                    ON CONFLICT (run_id) DO UPDATE SET
                        original_tokens = {excluded_kw}.original_tokens,
                        optimized_tokens = {excluded_kw}.optimized_tokens,
                        tokens_saved = {excluded_kw}.tokens_saved,
                        reduction_percentage = {excluded_kw}.reduction_percentage,
                        accuracy = {excluded_kw}.accuracy,
                        provider_confirmed_original_tokens = {excluded_kw}.provider_confirmed_original_tokens,
                        provider_confirmed_input_tokens = {excluded_kw}.provider_confirmed_input_tokens
                    """,
                    (
                        tok_pk,
                        run_pk,
                        int(run["original_tokens"]),
                        int(run["optimized_tokens"]),
                        int(run["tokens_saved"]),
                        float(run["reduction_percentage"]),
                        str(run["accuracy"]),
                        run.get("provider_confirmed_original_tokens"),
                        run.get("provider_confirmed_input_tokens"),
                    ),
                )

                if run.get("pricing_version"):
                    cost_pk = f"cost_{run_pk}"
                    self._execute(
                        f"""
                        INSERT INTO cost_metrics (
                            id, run_id, pricing_version,
                            estimated_cost_avoided_usd, provider_confirmed_cost_avoided_usd
                        )
                        VALUES (?, ?, ?, ?, ?)
                        ON CONFLICT (run_id) DO UPDATE SET
                            pricing_version = {excluded_kw}.pricing_version,
                            estimated_cost_avoided_usd = {excluded_kw}.estimated_cost_avoided_usd,
                            provider_confirmed_cost_avoided_usd = {excluded_kw}.provider_confirmed_cost_avoided_usd
                        """,
                        (
                            cost_pk,
                            run_pk,
                            str(run["pricing_version"]),
                            float(run.get("estimated_cost_avoided_usd", 0.0)),
                            run.get("provider_confirmed_cost_avoided_usd"),
                        ),
                    )
                inserted_or_updated += 1

            self._execute(
                "UPDATE installations SET last_active_at = ? WHERE id = ?",
                (now_fallback, installation_id),
            )
            self._conn.commit()
        return inserted_or_updated, len(runs)

    def sync_rule(
        self,
        *,
        rule_id: str,
        installation_id: str,
        project_id: str | None,
        scope: str,
        mode: str,
        preserve_identifiers: bool,
        allow_ai_semantic_compression: bool,
        min_meaningful_savings_tokens: int,
        rules: dict[str, Any],
        version: int,
        prefer_local_override: bool,
    ) -> dict[str, Any]:
        """Monotonic version conflict resolution for synced optimization_rules."""
        rule_pk = f"{installation_id}:{rule_id}"
        with self._lock:
            existing = self._fetchone("SELECT * FROM optimization_rules WHERE id = ?", (rule_pk,))
            if existing is not None and not prefer_local_override and int(existing["version"]) > version:
                return {
                    "resolution": "conflict_cloud_newer",
                    "rule": self._serialize_rule_row(existing),
                }

            effective_version = (
                max(version, int(existing["version"]) + 1)
                if (existing is not None and prefer_local_override and int(existing["version"]) >= version)
                else version
            )
            p_ident: Any = preserve_identifiers if self._is_pg else (1 if preserve_identifiers else 0)
            p_ai: Any = (
                allow_ai_semantic_compression
                if self._is_pg
                else (1 if allow_ai_semantic_compression else 0)
            )
            rules_str = json.dumps(rules)
            now_val = datetime.now(tz=UTC) if self._is_pg else datetime.now(tz=UTC).strftime("%Y-%m-%d %H:%M:%S")
            excluded_kw = "EXCLUDED" if self._is_pg else "excluded"

            if self._is_pg:
                self._execute(
                    f"""
                    INSERT INTO optimization_rules (
                        id, installation_id, project_id, scope, mode,
                        preserve_identifiers, allow_ai_semantic_compression,
                        min_meaningful_savings_tokens, rules_json, version, updated_at
                    )
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?::jsonb, ?, ?)
                    ON CONFLICT (id) DO UPDATE SET
                        project_id = {excluded_kw}.project_id,
                        scope = {excluded_kw}.scope,
                        mode = {excluded_kw}.mode,
                        preserve_identifiers = {excluded_kw}.preserve_identifiers,
                        allow_ai_semantic_compression = {excluded_kw}.allow_ai_semantic_compression,
                        min_meaningful_savings_tokens = {excluded_kw}.min_meaningful_savings_tokens,
                        rules_json = {excluded_kw}.rules_json,
                        version = {excluded_kw}.version,
                        updated_at = {excluded_kw}.updated_at
                    """,
                    (
                        rule_pk,
                        installation_id,
                        project_id,
                        scope,
                        mode,
                        p_ident,
                        p_ai,
                        min_meaningful_savings_tokens,
                        rules_str,
                        effective_version,
                        now_val,
                    ),
                )
            else:
                self._execute(
                    f"""
                    INSERT INTO optimization_rules (
                        id, installation_id, project_id, scope, mode,
                        preserve_identifiers, allow_ai_semantic_compression,
                        min_meaningful_savings_tokens, rules_json, version, updated_at
                    )
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                    ON CONFLICT (id) DO UPDATE SET
                        project_id = {excluded_kw}.project_id,
                        scope = {excluded_kw}.scope,
                        mode = {excluded_kw}.mode,
                        preserve_identifiers = {excluded_kw}.preserve_identifiers,
                        allow_ai_semantic_compression = {excluded_kw}.allow_ai_semantic_compression,
                        min_meaningful_savings_tokens = {excluded_kw}.min_meaningful_savings_tokens,
                        rules_json = {excluded_kw}.rules_json,
                        version = {excluded_kw}.version,
                        updated_at = {excluded_kw}.updated_at
                    """,
                    (
                        rule_pk,
                        installation_id,
                        project_id,
                        scope,
                        mode,
                        p_ident,
                        p_ai,
                        min_meaningful_savings_tokens,
                        rules_str,
                        effective_version,
                        now_val,
                    ),
                )
            self._conn.commit()
            updated = self._fetchone("SELECT * FROM optimization_rules WHERE id = ?", (rule_pk,))
            assert updated is not None
            return {"resolution": "applied", "rule": self._serialize_rule_row(updated)}

    def _serialize_rule_row(self, row: dict[str, Any]) -> dict[str, Any]:
        return {
            "id": row["id"],
            "installation_id": row["installation_id"],
            "project_id": row["project_id"],
            "scope": row["scope"],
            "mode": row["mode"],
            "preserve_identifiers": bool(row["preserve_identifiers"]),
            "allow_ai_semantic_compression": bool(row["allow_ai_semantic_compression"]),
            "min_meaningful_savings_tokens": int(row["min_meaningful_savings_tokens"]),
            "rules": _parse_json_field(row["rules_json"], {}),
            "version": int(row["version"]),
            "updated_at": _to_iso_str(row["updated_at"]),
        }

    def list_rules(self, installation_id: str) -> list[dict[str, Any]]:
        rows = self._fetchall(
            "SELECT * FROM optimization_rules WHERE installation_id = ? ORDER BY updated_at DESC",
            (installation_id,),
        )
        return [self._serialize_rule_row(r) for r in rows]

    def upsert_benchmark_results(self, results: list[dict[str, Any]]) -> int:
        excluded_kw = "EXCLUDED" if self._is_pg else "excluded"
        with self._lock:
            for item in results:
                provider = str(item.get("provider", "openai")).strip().lower()
                model = str(item.get("model", "gpt-4o")).strip()
                model_pk = f"{provider}:{model}"
                model_row = self._fetchone("SELECT id FROM models WHERE id = ?", (model_pk,))
                self._execute(
                    f"""
                    INSERT INTO benchmark_results (
                        id, suite_name, category, dataset_version, engine_version,
                        model_id, model_name, optimization_mode, sample_count,
                        unit_test_pass_rate, constraint_preservation_rate,
                        identifier_preservation_rate, median_reduction_pct,
                        p50_latency_ms, p95_latency_ms, negative_savings_count,
                        paired_quality_delta, report_uri
                    )
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                    ON CONFLICT (id) DO UPDATE SET
                        sample_count = {excluded_kw}.sample_count,
                        unit_test_pass_rate = {excluded_kw}.unit_test_pass_rate,
                        constraint_preservation_rate = {excluded_kw}.constraint_preservation_rate,
                        identifier_preservation_rate = {excluded_kw}.identifier_preservation_rate,
                        median_reduction_pct = {excluded_kw}.median_reduction_pct,
                        p50_latency_ms = {excluded_kw}.p50_latency_ms,
                        p95_latency_ms = {excluded_kw}.p95_latency_ms,
                        negative_savings_count = {excluded_kw}.negative_savings_count,
                        paired_quality_delta = {excluded_kw}.paired_quality_delta,
                        report_uri = {excluded_kw}.report_uri
                    """,
                    (
                        item["id"],
                        item["suite_name"],
                        item["category"],
                        item["dataset_version"],
                        item["engine_version"],
                        model_row["id"] if model_row else None,
                        model,
                        str(item["optimization_mode"]),
                        int(item["sample_count"]),
                        item.get("unit_test_pass_rate"),
                        item.get("constraint_preservation_rate"),
                        item.get("identifier_preservation_rate"),
                        item.get("median_reduction_pct"),
                        item.get("p50_latency_ms"),
                        item.get("p95_latency_ms"),
                        int(item.get("negative_savings_count", 0)),
                        item.get("paired_quality_delta"),
                        item.get("report_uri"),
                    ),
                )
            self._conn.commit()
        return len(results)

    def fetch_analytics_rows(
        self,
        *,
        user_id: str | None = None,
        provider: str | None = None,
        model: str | None = None,
        integration: str | None = None,
        mode: str | None = None,
        accuracy: str | None = None,
        device_id: str | None = None,
    ) -> list[dict[str, Any]]:
        clauses: list[str] = []
        params: list[Any] = []
        if user_id:
            clauses.append("i.user_id = ?")
            params.append(user_id)
        if provider:
            clauses.append("COALESCE(r.provider_id, 'unknown') = ?")
            params.append(provider.strip().lower())
        if model:
            clauses.append("r.model_name = ?")
            params.append(model)
        if integration:
            clauses.append("r.integration = ?")
            params.append(integration)
        if mode:
            clauses.append("r.optimization_mode = ?")
            params.append(mode)
        if accuracy:
            clauses.append("m.accuracy = ?")
            params.append(accuracy)
        if device_id:
            clauses.append("r.device_id = ?")
            params.append(device_id)

        where_sql = f"WHERE {' AND '.join(clauses)}" if clauses else ""
        rows = self._fetchall(
            f"""
            SELECT
                r.id,
                r.run_id,
                r.installation_id,
                r.device_id,
                COALESCE(d.device_label, r.installation_id) AS device_label,
                COALESCE(r.provider_id, 'local') AS provider,
                r.model_name,
                r.integration,
                r.content_type,
                r.optimization_mode,
                r.status,
                r.methods_json,
                r.warnings_json,
                r.duration_ms,
                r.created_at,
                m.original_tokens,
                m.optimized_tokens,
                m.tokens_saved,
                m.reduction_percentage,
                m.accuracy,
                m.provider_confirmed_original_tokens,
                m.provider_confirmed_input_tokens,
                c.pricing_version,
                COALESCE(c.estimated_cost_avoided_usd, 0.0) AS estimated_cost_avoided_usd,
                c.provider_confirmed_cost_avoided_usd
            FROM optimization_runs r
            JOIN installations i ON i.id = r.installation_id
            LEFT JOIN devices d ON d.id = r.device_id
            JOIN token_metrics m ON m.run_id = r.id
            LEFT JOIN cost_metrics c ON c.run_id = r.id
            {where_sql}
            ORDER BY r.created_at ASC
            """,
            tuple(params),
        )
        for row in rows:
            row["methods"] = _parse_json_field(row.pop("methods_json", "[]"), [])
            row["warnings"] = _parse_json_field(row.pop("warnings_json", "[]"), [])
            row["created_at"] = _to_iso_str(row["created_at"])
        return rows

    def fetch_benchmarks(self) -> list[dict[str, Any]]:
        rows = self._fetchall(
            """
            SELECT
                id, suite_name, category, dataset_version, engine_version,
                model_name, optimization_mode, sample_count,
                unit_test_pass_rate, constraint_preservation_rate,
                identifier_preservation_rate, median_reduction_pct,
                p50_latency_ms, p95_latency_ms, negative_savings_count,
                paired_quality_delta, report_uri, executed_at
            FROM benchmark_results
            ORDER BY category ASC, executed_at DESC
            """
        )
        for row in rows:
            row["executed_at"] = _to_iso_str(row["executed_at"])
        return rows

    def close(self) -> None:
        with self._lock:
            self._conn.close()
