"""Typed configuration and bind-address safety guards for Local Runtime."""

from __future__ import annotations

import ipaddress
import os
from dataclasses import dataclass, field
from pathlib import Path

DEFAULT_HOST = "127.0.0.1"
DEFAULT_PORT = 4765
RUNTIME_VERSION = "0.2.0"


def default_data_dir() -> Path:
    env_dir = os.environ.get("PROJECT_T_DATA_DIR")
    if env_dir:
        return Path(env_dir).expanduser().resolve()
    return (Path.home() / ".project-t").resolve()


def is_loopback_host(host: str) -> bool:
    normalized = host.strip().lower()
    if normalized in {"localhost", "127.0.0.1", "::1"}:
        return True
    try:
        return ipaddress.ip_address(normalized).is_loopback
    except ValueError:
        return False


@dataclass(frozen=True, slots=True)
class RuntimeConfig:
    """Configuration governing local HTTP transport, limits, and security boundaries."""

    host: str = DEFAULT_HOST
    port: int = DEFAULT_PORT
    data_dir: Path = field(default_factory=default_data_dir)
    db_path: Path | None = None
    allow_non_loopback_bind: bool = False
    max_body_bytes: int = 2_097_152  # 2 MiB
    request_timeout_seconds: float = 15.0
    rate_limit_requests: int = 120
    rate_limit_window_seconds: int = 60
    allowed_origins: tuple[str, ...] = ()
    approved_workspaces: tuple[Path, ...] = ()
    use_os_keyring: bool = True
    allow_tiktoken: bool = True

    def __post_init__(self) -> None:
        if not self.allow_non_loopback_bind and not is_loopback_host(self.host):
            raise ValueError(
                f"Refusing non-loopback bind host '{self.host}'. "
                "Local runtime must bind to 127.0.0.1 / loopback by default."
            )
        for origin in self.allowed_origins:
            if origin.strip() == "*":
                raise ValueError("Wildcard '*' CORS origin is prohibited.")

    @property
    def resolved_db_path(self) -> Path:
        if self.db_path is not None:
            return self.db_path
        return self.data_dir / "local_runtime.db"

    @property
    def allowed_hosts(self) -> frozenset[str]:
        return frozenset(
            {
                "127.0.0.1",
                "localhost",
                f"127.0.0.1:{self.port}",
                f"localhost:{self.port}",
                "[::1]",
                f"[::1]:{self.port}",
                "testserver",  # Starlette/FastAPI TestClient internal host
            }
        )
