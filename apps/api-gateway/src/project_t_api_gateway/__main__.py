"""CLI entrypoint for Project T API Gateway."""

from __future__ import annotations

import argparse

import uvicorn

from .config import DEFAULT_GATEWAY_HOST, DEFAULT_GATEWAY_PORT, GatewayConfig
from .routes import create_gateway_app


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Project T API Gateway CLI")
    subparsers = parser.add_subparsers(dest="command", required=True)
    serve = subparsers.add_parser("serve", help="Start the API Gateway server")
    serve.add_argument("--host", default=DEFAULT_GATEWAY_HOST)
    serve.add_argument("--port", type=int, default=DEFAULT_GATEWAY_PORT)

    args = parser.parse_args(argv)
    if args.command == "serve":
        cfg = GatewayConfig(host=args.host, port=args.port)
        app = create_gateway_app(config=cfg)
        uvicorn.run(app, host=cfg.host, port=cfg.port, log_level="warning")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
