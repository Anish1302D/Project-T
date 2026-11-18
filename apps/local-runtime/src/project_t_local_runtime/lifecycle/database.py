"""SQLite persistence, migration bootstrap, metadata-only run recording, and retention purge."""

from __future__ import annotations

import json
import sqlite3
import statistics
import threading
import uuid
from datetime import UTC, datetime, timedelta
from pathlib import Path

from project_t_contracts import (
    IntegrationSource,
    MetricsSummaryResponse,
    OptimizationMode,
    OptimizationResultWire,
    OptimizationStatus,
    RuntimeSettings,
    RuntimeSettingsUpdate,
)
from project_t_provider_adapters import ProviderRegistry

_DEFAULT_MIGRATION_PATH = (
    Path(__file__).resolve().parents[5]
    / "infrastructure"
    / "database"
    / "sqlite"
    / "001_initial_schema.sql"
)


class LocalDatabase:
    """Thread-safe SQLite store implementing metadata-only default persistence."""

    def __init__(
        self,
        db_path: Path | str,
        *,
        migration_path: Path | None = None,
    ) -> None:
        self._db_path = str(db_path)
        self._migration_path = migration_path or _DEFAULT_MIGRATION_PATH
        self._lock = threading.Lock()
        if self._db_path != ":memory:":
            Path(self._db_path).parent.mkdir(parents=True, exist_ok=True)
        self._conn = sqlite3.connect(self._db_path, check_same_thread=False)
        self._conn.row_factory = sqlite3.Row
        with self._lock:
            self._conn.execute("PRAGMA foreign_keys = ON;")
            if self._db_path != ":memory:":
                self._conn.execute("PRAGMA journal_mode = WAL;")

    def initialize(
        self,
        *,
        installation_id: str,
        runtime_version: str,
        registry: ProviderRegistry,
    ) -> None:
        """Execute initial schema DDL and seed installation, providers, models, and default rules."""
        sql_script = self._migration_path.read_text(encoding="utf-8")
        with self._lock:
            self._conn.executescript(sql_script)
            self._conn.execute("PRAGMA foreign_keys = ON;")
            self._conn.execute(
                """
                INSERT INTO installations (id, runtime_version, schema_version, sync_enabled)
                VALUES (?, ?, '1.0', 0)
                ON CONFLICT(id) DO UPDATE SET
                    runtime_version = excluded.runtime_version,
                    last_active_at = CURRENT_TIMESTAMP
                """,
                (installation_id, runtime_version),
            )
            for provider in registry.list_catalog_entries():
                self._conn.execute(
                    """
                    INSERT OR IGNORE INTO providers (id, display_name, tokenizer_family, is_enabled)
                    VALUES (?, ?, ?, 1)
                    """,
                    (provider.id, provider.display_name, provider.id),
                )
                for model in provider.models:
                    model_pk = f"{provider.id}:{model.model_name}"
                    self._conn.execute(
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
            # Ensure global default settings row exists
            existing_rule = self._conn.execute(
                "SELECT id FROM optimization_rules WHERE id = 'global_default'"
            ).fetchone()
            if existing_rule is None:
                defaults = RuntimeSettings()
                self._conn.execute(
                    """
                    INSERT INTO optimization_rules (
                        id, installation_id, scope, mode, preserve_identifiers,
                        allow_ai_semantic_compression, rules_json
                    )
                    VALUES ('global_default', ?, 'global', ?, ?, ?, ?)
                    """,
                    (
                        installation_id,
                        defaults.default_mode,
                        1 if defaults.preserve_identifiers else 0,
                        1 if defaults.allow_ai_semantic_compression else 0,
                        json.dumps(defaults.model_dump()),
                    ),
                )
            self._conn.commit()

    def is_ready(self) -> bool:
        try:
            with self._lock:
                self._conn.execute("SELECT 1").fetchone()
            return True
        except sqlite3.Error:
            return False

    def record_optimization_run(
        self,
        *,
        installation_id: str,
        integration: IntegrationSource | str,
        provider: str,
        model: str,
        content_type: str,
        status: OptimizationStatus,
        result: OptimizationResultWire,
    ) -> str:
        """
        Persist metadata-only run & token metrics in SQLite.

        Never stores raw prompt text, optimized prompt text, source code, or terminal logs.
        """
        run_id = f"run_{uuid.uuid4().hex[:16]}"
        metric_id = f"tok_{uuid.uuid4().hex[:16]}"
        provider_norm = provider.strip().lower()
        model_pk = f"{provider_norm}:{model}"

        with self._lock:
            prov_row = self._conn.execute(
                "SELECT id FROM providers WHERE id = ?", (provider_norm,)
            ).fetchone()
            model_row = self._conn.execute(
                "SELECT id FROM models WHERE id = ?", (model_pk,)
            ).fetchone()

            self._conn.execute(
                """
                INSERT INTO optimization_runs (
                    id, request_id, installation_id, provider_id, model_id,
                    integration, content_type, optimization_mode, status,
                    methods_json, warnings_json, quality_score, duration_ms
                )
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    run_id,
                    result.request_id,
                    installation_id,
                    prov_row["id"] if prov_row else None,
                    model_row["id"] if model_row else None,
                    str(integration),
                    content_type,
                    str(result.optimization.mode),
                    status.value,
                    json.dumps(result.optimization.methods),
                    json.dumps(result.warnings),
                    result.validation.quality_score,
                    result.duration_ms,
                ),
            )
            self._conn.execute(
                """
                INSERT INTO token_metrics (
                    id, run_id, original_tokens, optimized_tokens,
                    tokens_saved, reduction_percentage, accuracy
                )
                VALUES (?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    metric_id,
                    run_id,
                    result.tokens.original,
                    result.tokens.optimized,
                    result.tokens.saved,
                    result.tokens.reduction_percentage,
                    str(result.tokens.accuracy),
                ),
            )
            self._conn.commit()
        return run_id

    def query_metrics(
        self,
        *,
        integration: IntegrationSource | str | None = None,
        window_days: int = 30,
    ) -> MetricsSummaryResponse:
        cutoff = (datetime.now(tz=UTC) - timedelta(days=window_days)).strftime("%Y-%m-%d %H:%M:%S")
        params: list[object] = [cutoff]
        where_extra = ""
        if integration is not None:
            where_extra = " AND r.integration = ?"
            params.append(str(integration))

        query = f"""
            SELECT
                r.status,
                m.original_tokens,
                m.optimized_tokens,
                m.tokens_saved,
                m.reduction_percentage,
                m.accuracy
            FROM optimization_runs r
            JOIN token_metrics m ON m.run_id = r.id
            WHERE r.created_at >= ?{where_extra}
        """
        with self._lock:
            rows = self._conn.execute(query, params).fetchall()

        if not rows:
            return MetricsSummaryResponse(
                total_runs=0,
                total_original_tokens=0,
                total_optimized_tokens=0,
                total_tokens_saved=0,
                median_reduction_percentage=0.0,
                fallback_count=0,
                by_accuracy={"exact": 0, "estimated": 0},
            )

        total_orig = sum(int(r["original_tokens"]) for r in rows)
        total_opt = sum(int(r["optimized_tokens"]) for r in rows)
        total_saved = sum(int(r["tokens_saved"]) for r in rows)
        fallbacks = sum(1 for r in rows if r["status"] != OptimizationStatus.VALIDATED.value)
        reductions = [float(r["reduction_percentage"]) for r in rows]
        by_accuracy: dict[str, int] = {"exact": 0, "estimated": 0}
        for r in rows:
            acc = str(r["accuracy"])
            by_accuracy[acc] = by_accuracy.get(acc, 0) + 1

        return MetricsSummaryResponse(
            total_runs=len(rows),
            total_original_tokens=total_orig,
            total_optimized_tokens=total_opt,
            total_tokens_saved=total_saved,
            median_reduction_percentage=round(statistics.median(reductions), 2),
            fallback_count=fallbacks,
            by_accuracy=by_accuracy,
        )

    def get_settings(self) -> RuntimeSettings:
        with self._lock:
            row = self._conn.execute(
                "SELECT rules_json FROM optimization_rules WHERE id = 'global_default'"
            ).fetchone()
        if row is None:
            return RuntimeSettings()
        data = json.loads(row["rules_json"])
        return RuntimeSettings(**data)

    def update_settings(self, update: RuntimeSettingsUpdate) -> RuntimeSettings:
        current = self.get_settings()
        merged = current.model_copy(update=update.model_dump(exclude_none=True))
        with self._lock:
            self._conn.execute(
                """
                UPDATE optimization_rules
                SET mode = ?,
                    preserve_identifiers = ?,
                    allow_ai_semantic_compression = ?,
                    rules_json = ?,
                    version = version + 1,
                    updated_at = CURRENT_TIMESTAMP
                WHERE id = 'global_default'
                """,
                (
                    str(merged.default_mode),
                    1 if merged.preserve_identifiers else 0,
                    1 if merged.allow_ai_semantic_compression else 0,
                    json.dumps(merged.model_dump()),
                ),
            )
            self._conn.commit()
        return merged

    def purge_expired(self, *, retention_days: int) -> int:
        cutoff = (datetime.now(tz=UTC) - timedelta(days=retention_days)).strftime("%Y-%m-%d %H:%M:%S")
        with self._lock:
            cur = self._conn.execute(
                "DELETE FROM optimization_runs WHERE created_at < ?", (cutoff,)
            )
            now_iso = datetime.now(tz=UTC).isoformat()
            self._conn.execute(
                "DELETE FROM context_fingerprints WHERE fresh_until IS NOT NULL AND fresh_until < ?",
                (now_iso,),
            )
            self._conn.commit()
            return cur.rowcount

    def close(self) -> None:
        with self._lock:
            self._conn.close()
