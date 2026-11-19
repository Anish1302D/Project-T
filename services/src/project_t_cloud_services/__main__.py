"""CLI entrypoint running the Project T Cloud Control Plane server."""

from __future__ import annotations

import uvicorn

from .app import create_control_plane_app
from .config import CloudConfig


def main() -> int:
    cfg = CloudConfig()
    uvicorn.run(
        create_control_plane_app(cfg),
        host=cfg.host,
        port=cfg.port,
        log_level="info",
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
