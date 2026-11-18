"""Project- and version-scoped context fingerprint store using SQLite."""

from __future__ import annotations

import hashlib
import sqlite3
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta


@dataclass(frozen=True, slots=True)
class ContextFingerprintRecord:
    """Scoped fingerprint record aligned with schema.sql context_fingerprints."""

    project_id: str
    content_version: str
    file_hash: str
    block_hash: str
    token_count: int
    accuracy: str
    fresh_until: str | None = None


def compute_sha256(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


class ContextFingerprintStore:
    """
    Manages project- and content-version-scoped context fingerprints in SQLite.

    Enforces strict project isolation and freshness invalidation when file_hash changes.
    """

    def __init__(self, conn: sqlite3.Connection | None = None) -> None:
        self._conn = conn if conn is not None else sqlite3.connect(":memory:")
        self._ensure_schema()

    def _ensure_schema(self) -> None:
        self._conn.execute(
            """
            CREATE TABLE IF NOT EXISTS context_fingerprints (
                id TEXT PRIMARY KEY,
                project_id TEXT NOT NULL,
                content_version TEXT NOT NULL,
                file_hash TEXT NOT NULL,
                block_hash TEXT NOT NULL,
                simhash_64 TEXT,
                token_count INTEGER NOT NULL DEFAULT 0,
                accuracy TEXT NOT NULL DEFAULT 'estimated',
                fresh_until TEXT,
                created_at TEXT NOT NULL DEFAULT (CURRENT_TIMESTAMP),
                UNIQUE (project_id, content_version, block_hash)
            )
            """
        )
        self._conn.execute(
            "CREATE INDEX IF NOT EXISTS idx_fp_scope ON context_fingerprints(project_id, file_hash, content_version)"
        )
        self._conn.commit()

    def put(
        self,
        *,
        project_id: str,
        content_version: str,
        file_hash: str,
        block_text: str,
        token_count: int,
        accuracy: str = "estimated",
        ttl_seconds: int | None = None,
    ) -> ContextFingerprintRecord:
        block_hash = compute_sha256(block_text.strip())
        fresh_until = (
            (datetime.now(tz=UTC) + timedelta(seconds=ttl_seconds)).isoformat()
            if ttl_seconds is not None
            else None
        )
        rec_id = compute_sha256(f"{project_id}:{content_version}:{block_hash}")[:32]
        self._conn.execute(
            """
            INSERT INTO context_fingerprints
                (id, project_id, content_version, file_hash, block_hash, token_count, accuracy, fresh_until)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            ON CONFLICT(project_id, content_version, block_hash) DO UPDATE SET
                file_hash = excluded.file_hash,
                token_count = excluded.token_count,
                accuracy = excluded.accuracy,
                fresh_until = excluded.fresh_until
            """,
            (rec_id, project_id, content_version, file_hash, block_hash, token_count, accuracy, fresh_until),
        )
        self._conn.commit()
        return ContextFingerprintRecord(
            project_id=project_id,
            content_version=content_version,
            file_hash=file_hash,
            block_hash=block_hash,
            token_count=token_count,
            accuracy=accuracy,
            fresh_until=fresh_until,
        )

    def lookup(
        self,
        *,
        project_id: str,
        content_version: str,
        file_hash: str,
        block_text: str,
    ) -> ContextFingerprintRecord | None:
        block_hash = compute_sha256(block_text.strip())
        row = self._conn.execute(
            """
            SELECT project_id, content_version, file_hash, block_hash, token_count, accuracy, fresh_until
            FROM context_fingerprints
            WHERE project_id = ? AND content_version = ? AND file_hash = ? AND block_hash = ?
            """,
            (project_id, content_version, file_hash, block_hash),
        ).fetchone()
        if row is None:
            return None
        fresh_until = row[6]
        if fresh_until is not None and datetime.fromisoformat(fresh_until) < datetime.now(tz=UTC):
            return None
        return ContextFingerprintRecord(
            project_id=row[0],
            content_version=row[1],
            file_hash=row[2],
            block_hash=row[3],
            token_count=row[4],
            accuracy=row[5],
            fresh_until=fresh_until,
        )

    def invalidate_project_file(self, *, project_id: str, file_hash: str) -> int:
        cur = self._conn.execute(
            "DELETE FROM context_fingerprints WHERE project_id = ? AND file_hash = ?",
            (project_id, file_hash),
        )
        self._conn.commit()
        return cur.rowcount
