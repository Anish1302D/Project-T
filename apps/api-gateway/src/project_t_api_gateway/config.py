"""Configuration for Project T API Gateway."""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path

from project_t_local_runtime.config import default_data_dir

GATEWAY_VERSION = "0.5.0"
DEFAULT_GATEWAY_HOST = "127.0.0.1"
DEFAULT_GATEWAY_PORT = 4775


@dataclass(frozen=True, slots=True)
class GatewayConfig:
    """Configuration governing upstream endpoints, limits, and SQLite reconciliation store."""

    host: str = DEFAULT_GATEWAY_HOST
    port: int = DEFAULT_GATEWAY_PORT
    data_dir: Path = field(default_factory=default_data_dir)
    db_path: Path | None = None
    openai_base_url: str = "https://api.openai.com"
    anthropic_base_url: str = "https://api.anthropic.com"
    google_base_url: str = "https://generativelanguage.googleapis.com"
    upstream_timeout_seconds: float = 60.0
    optimization_timeout_seconds: float = 2.0
    max_body_bytes: int = 4_194_304  # 4 MiB
    allow_tiktoken: bool = True
    use_os_keyring: bool = False

    @property
    def resolved_db_path(self) -> Path:
        if self.db_path is not None:
            return self.db_path
        return self.data_dir / "gateway_usage.db"
