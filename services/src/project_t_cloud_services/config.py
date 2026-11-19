"""Configuration for the Project T Cloud Control Plane."""

from __future__ import annotations

import os
import secrets
from dataclasses import dataclass, field
from pathlib import Path

CLOUD_SERVICE_VERSION = "0.5.0"


def _default_cloud_origins() -> tuple[str, ...]:
    origins = [
        "http://127.0.0.1:5173",
        "http://localhost:5173",
        "http://127.0.0.1:4173",
        "http://localhost:4173",
    ]
    extra = os.environ.get("DASHBOARD_ORIGIN", "").strip()
    if extra and extra != "*":
        for item in extra.split(","):
            cleaned = item.strip().rstrip("/")
            if cleaned and cleaned not in origins:
                origins.append(cleaned)
    return tuple(origins)


@dataclass(frozen=True, slots=True)
class CloudConfig:
    """Typed configuration for authentication, Postgres/SQLite storage, and optional Redis."""

    host: str = field(default_factory=lambda: os.environ.get("CLOUD_HOST", "127.0.0.1"))
    port: int = field(default_factory=lambda: int(os.environ.get("CLOUD_PORT", "4780")))
    data_dir: Path = field(
        default_factory=lambda: Path(os.environ.get("PROJECT_T_CLOUD_DATA_DIR", str(Path.home() / ".project-t-cloud")))
    )
    database_url: str | None = field(default_factory=lambda: os.environ.get("DATABASE_URL"))
    redis_url: str | None = field(default_factory=lambda: os.environ.get("REDIS_URL"))
    jwt_secret: str = field(
        default_factory=lambda: os.environ.get("PROJECT_T_JWT_SECRET") or secrets.token_urlsafe(32)
    )
    jwt_ttl_seconds: int = 86_400
    allowed_origins: tuple[str, ...] = field(default_factory=_default_cloud_origins)

    @property
    def is_postgres(self) -> bool:
        return bool(
            self.database_url
            and self.database_url.strip().lower().startswith(("postgresql://", "postgres://"))
        )

    @property
    def resolved_sqlite_path(self) -> Path:
        if self.database_url and self.database_url.startswith("sqlite:///"):
            raw = self.database_url[len("sqlite:///"):]
            if raw == ":memory:":
                return Path(":memory:")
            return Path(raw)
        return self.data_dir / "cloud_control_plane.db"
