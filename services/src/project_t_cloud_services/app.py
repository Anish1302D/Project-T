"""FastAPI Cloud Control Plane application combining auth, metadata sync, and analytics."""

from __future__ import annotations

import logging
import re
from contextlib import asynccontextmanager

from fastapi import FastAPI, HTTPException, Request
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from project_t_provider_adapters import ProviderRegistry

from .analytics import AnalyticsCache, create_analytics_router
from .authentication import create_auth_router
from .cloud_sync import create_sync_router
from .config import CLOUD_SERVICE_VERSION, CloudConfig
from .storage import CloudDatabase

_SECRET_LOG_RE = re.compile(
    r"(Bearer\s+[A-Za-z0-9._\-+/=]+|\bsk-[A-Za-z0-9_-]{8,}|\bAIza[A-Za-z0-9_-]{12,})",
    re.IGNORECASE,
)


class _CloudRedactingFilter(logging.Filter):
    def filter(self, record: logging.LogRecord) -> bool:
        if isinstance(record.msg, str):
            record.msg = _SECRET_LOG_RE.sub("[REDACTED]", record.msg)
        if isinstance(record.args, tuple):
            record.args = tuple(
                _SECRET_LOG_RE.sub("[REDACTED]", a) if isinstance(a, str) else a for a in record.args
            )
        return True


logger = logging.getLogger("project_t.cloud_services")
if not any(isinstance(f, _CloudRedactingFilter) for f in logger.filters):
    logger.addFilter(_CloudRedactingFilter())


def create_control_plane_app(config: CloudConfig | None = None) -> FastAPI:
    """Create the optional Project T Cloud Control Plane FastAPI application."""
    cfg = config if config is not None else CloudConfig()
    registry = ProviderRegistry()
    db = CloudDatabase(
        database_url=cfg.database_url if cfg.is_postgres else None,
        sqlite_path=None if cfg.is_postgres else cfg.resolved_sqlite_path,
    )
    db.initialize(registry)
    cache = AnalyticsCache(redis_url=cfg.redis_url)

    @asynccontextmanager
    async def lifespan(_: FastAPI):
        try:
            yield
        finally:
            db.close()

    app = FastAPI(
        title="Project T Cloud Control Plane",
        version=CLOUD_SERVICE_VERSION,
        lifespan=lifespan,
    )
    app.state.cloud_db = db
    app.state.cloud_config = cfg

    app.add_middleware(
        CORSMiddleware,
        allow_origins=list(cfg.allowed_origins),
        allow_credentials=True,
        allow_methods=["GET", "POST", "PUT", "OPTIONS"],
        allow_headers=["Authorization", "Content-Type"],
    )

    @app.exception_handler(HTTPException)
    async def _http_exception_handler(_: Request, exc: HTTPException) -> JSONResponse:
        if isinstance(exc.detail, dict) and "error" in exc.detail:
            return JSONResponse(status_code=exc.status_code, content=exc.detail)
        return JSONResponse(
            status_code=exc.status_code,
            content={
                "error": {
                    "code": f"http_{exc.status_code}",
                    "message": str(exc.detail),
                }
            },
        )

    @app.exception_handler(RequestValidationError)
    async def _validation_error_handler(_: Request, exc: RequestValidationError) -> JSONResponse:
        locs = [
            f"{'.'.join(str(x) for x in err.get('loc', ()))}: {err.get('msg', 'invalid')}"
            for err in exc.errors()
        ]
        # Never echo input body fields cleanly per ADR-0011
        return JSONResponse(
            status_code=422,
            content={
                "error": {
                    "code": "sync_boundary_violation"
                    if any("extra_forbidden" in str(e.get("type", "")) for e in exc.errors())
                    else "validation_error",
                    "message": "; ".join(locs[:5]) or "Invalid request payload.",
                }
            },
        )

    @app.get("/health")
    def get_health() -> dict[str, object]:
        ready = db.is_ready()
        return {
            "status": "ok" if ready else "degraded",
            "version": CLOUD_SERVICE_VERSION,
            "database_backend": db.backend_name,
            "cache_backend": cache.backend_name,
            "db_ready": ready,
        }

    app.include_router(create_auth_router(db=db, config=cfg))
    app.include_router(create_sync_router(db=db, config=cfg, cache=cache))
    app.include_router(create_analytics_router(db=db, config=cfg, cache=cache))
    return app
