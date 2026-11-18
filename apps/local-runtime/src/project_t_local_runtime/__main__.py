"""CLI entrypoint for Project T Local Runtime."""

from __future__ import annotations

import argparse
from pathlib import Path

import uvicorn

from .auth import CredentialStore
from .config import DEFAULT_HOST, DEFAULT_PORT, RuntimeConfig, default_data_dir
from .server import create_app


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Project T Local Runtime CLI")
    subparsers = parser.add_subparsers(dest="command", required=True)

    serve_cmd = subparsers.add_parser("serve", help="Start the local HTTP runtime")
    serve_cmd.add_argument("--host", default=DEFAULT_HOST)
    serve_cmd.add_argument("--port", type=int, default=DEFAULT_PORT)
    serve_cmd.add_argument("--approve-workspace", action="append", default=[])
    serve_cmd.add_argument("--allow-origin", action="append", default=[])

    subparsers.add_parser("rotate-token", help="Rotate the installation bearer token")

    status_cmd = subparsers.add_parser("status", help="Show installation metadata")
    status_cmd.add_argument(
        "--reveal-token",
        action="store_true",
        help="Print installation bearer token for explicit client pairing",
    )

    args = parser.parse_args(argv)
    data_dir = default_data_dir()

    if args.command == "rotate-token":
        creds = CredentialStore(data_dir).rotate_token()
        print(f"Rotated bearer token for {creds.installation_id} (backend={creds.storage_backend}).")
        return 0

    if args.command == "status":
        creds = CredentialStore(data_dir).load_or_create()
        print(f"Installation ID: {creds.installation_id}")
        print(f"Token backend:   {creds.storage_backend}")
        if args.reveal_token:
            print(f"Bearer token:    {creds.bearer_token}")
        return 0

    config = RuntimeConfig(
        host=args.host,
        port=args.port,
        data_dir=data_dir,
        approved_workspaces=tuple(Path(p).expanduser().resolve() for p in args.approve_workspace),
        allowed_origins=tuple(args.allow_origin),
    )
    app = create_app(config=config)
    uvicorn.run(app, host=config.host, port=config.port, log_level="warning")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
