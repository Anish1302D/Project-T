"""FastAPI local runtime server exposing authenticated /api/v1 endpoints."""

from __future__ import annotations

import asyncio
import logging
import uuid
from contextlib import asynccontextmanager
from typing import Annotated

from fastapi import APIRouter, Depends, FastAPI, Query, Request, Response
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from project_t_contracts import (
    AnalyzeRequest,
    AnalyzeResponse,
    ContextCompressRequest,
    ContextSelectRequest,
    ContextSelectResponse,
    ErrorDetail,
    ErrorResponse,
    HealthResponse,
    IntegrationSource,
    LogCompressRequest,
    MetricsSummaryResponse,
    OptimizationRequestWire,
    OptimizationResultWire,
    ProvidersResponse,
    RuntimeSettings,
    RuntimeSettingsUpdate,
    TokenCountRequest,
    TokenCountResult,
)

from ..auth import (
    SecretRedactingFilter,
    SlidingWindowRateLimiter,
    is_allowed_host,
    is_allowed_origin,
    redact_sensitive_text,
    verify_bearer_token,
)
from ..config import RUNTIME_VERSION, RuntimeConfig
from ..lifecycle import LocalRuntimeService, WorkspaceForbiddenError

logger = logging.getLogger("project_t.local_runtime")
if not any(isinstance(f, SecretRedactingFilter) for f in logger.filters):
    logger.addFilter(SecretRedactingFilter())

_bearer_scheme = HTTPBearer(auto_error=False)


def _error_json(
    status_code: int,
    *,
    code: str,
    message: str,
    request_id: str | None = None,
) -> JSONResponse:
    payload = ErrorResponse(
        error=ErrorDetail(
            code=code,
            message=redact_sensitive_text(message),
            request_id=request_id,
        )
    )
    return JSONResponse(status_code=status_code, content=payload.model_dump(exclude_none=True))


def create_app(
    *,
    config: RuntimeConfig | None = None,
    service: LocalRuntimeService | None = None,
) -> FastAPI:
    """Create the FastAPI Local Runtime application with strict security guards."""
    owns_service = service is None
    runtime_service = service if service is not None else LocalRuntimeService(config=config)
    runtime_config = runtime_service.config
    rate_limiter = SlidingWindowRateLimiter(
        max_requests=runtime_config.rate_limit_requests,
        window_seconds=runtime_config.rate_limit_window_seconds,
    )

    @asynccontextmanager
    async def lifespan(_: FastAPI):
        try:
            yield
        finally:
            if owns_service:
                runtime_service.close()

    app = FastAPI(
        title="Project T Local Runtime API",
        version=RUNTIME_VERSION,
        lifespan=lifespan,
    )
    app.state.runtime_service = runtime_service

    @app.middleware("http")
    async def security_gate_middleware(request: Request, call_next) -> Response:  # type: ignore[no-untyped-def]
        request_id = f"req_{uuid.uuid4().hex[:12]}"
        request.state.request_id = request_id

        # 1. DNS-rebinding defense: verify Host header
        host_header = request.headers.get("host")
        if not is_allowed_host(host_header, runtime_config.allowed_hosts):
            return _error_json(
                403,
                code="forbidden_origin",
                message="Disallowed Host header.",
                request_id=request_id,
            )

        # 2. Strict CORS & Origin allowlist check
        origin_header = request.headers.get("origin")
        if not is_allowed_origin(origin_header, runtime_config.allowed_origins):
            return _error_json(
                403,
                code="forbidden_origin",
                message="Origin is not in the configured allowlist.",
                request_id=request_id,
            )

        if request.method == "OPTIONS":
            headers = {
                "Vary": "Origin",
                "Access-Control-Allow-Methods": "GET, POST, PUT, OPTIONS",
                "Access-Control-Allow-Headers": "Authorization, Content-Type",
            }
            if origin_header:
                headers["Access-Control-Allow-Origin"] = origin_header.strip().rstrip("/")
            return Response(status_code=204, headers=headers)

        path = request.url.path
        is_health_or_docs = path in {"/api/v1/health", "/openapi.json"}

        if not is_health_or_docs:
            # 3. Bearer token verification (constant-time)
            auth_header = request.headers.get("authorization")
            if not verify_bearer_token(auth_header, runtime_service.credentials.bearer_token):
                return _error_json(
                    401,
                    code="unauthorized",
                    message="Missing or invalid installation bearer token.",
                    request_id=request_id,
                )

            # 4. Sliding-window local rate limit
            if not rate_limiter.allow_request():
                return _error_json(
                    429,
                    code="rate_limit_exceeded",
                    message="Local rate limit exceeded.",
                    request_id=request_id,
                )

            # 5. Request body size limit
            content_length = request.headers.get("content-length")
            if content_length is not None:
                try:
                    if int(content_length) > runtime_config.max_body_bytes:
                        return _error_json(
                            413,
                            code="payload_too_large",
                            message=f"Request body exceeds limit of {runtime_config.max_body_bytes} bytes.",
                            request_id=request_id,
                        )
                except ValueError:
                    return _error_json(
                        400,
                        code="invalid_request",
                        message="Invalid Content-Length header.",
                        request_id=request_id,
                    )

            body = await request.body()
            if len(body) > runtime_config.max_body_bytes:
                return _error_json(
                    413,
                    code="payload_too_large",
                    message=f"Request body exceeds limit of {runtime_config.max_body_bytes} bytes.",
                    request_id=request_id,
                )

        try:
            response = await asyncio.wait_for(
                call_next(request),
                timeout=runtime_config.request_timeout_seconds,
            )
        except TimeoutError:
            return _error_json(
                504,
                code="optimization_timeout",
                message="Request execution budget exceeded.",
                request_id=request_id,
            )

        if origin_header:
            response.headers["Access-Control-Allow-Origin"] = origin_header.strip().rstrip("/")
            response.headers["Vary"] = "Origin"
        return response

    @app.exception_handler(RequestValidationError)
    async def validation_exception_handler(request: Request, exc: RequestValidationError) -> JSONResponse:
        req_id = getattr(request.state, "request_id", None)
        # Never echo raw input values; report field paths and constraint messages only.
        sanitized_fields = [
            f"{'.'.join(str(p) for p in err.get('loc', ()))}: {err.get('msg', 'invalid')}"
            for err in exc.errors()
        ]
        summary = "; ".join(sanitized_fields[:5]) or "Request schema validation failed."
        return _error_json(
            422,
            code="validation_error",
            message=summary,
            request_id=req_id,
        )

    @app.exception_handler(WorkspaceForbiddenError)
    async def workspace_forbidden_handler(request: Request, exc: WorkspaceForbiddenError) -> JSONResponse:
        req_id = getattr(request.state, "request_id", None)
        return _error_json(
            403,
            code="forbidden_workspace",
            message=str(exc),
            request_id=req_id,
        )

    @app.exception_handler(Exception)
    async def unhandled_exception_handler(request: Request, exc: Exception) -> JSONResponse:
        req_id = getattr(request.state, "request_id", None)
        logger.error("Unhandled local runtime error (%s): %s", type(exc).__name__, req_id)
        return _error_json(
            500,
            code="internal_error",
            message="An internal runtime error occurred.",
            request_id=req_id,
        )

    def _require_bearer_doc(
        _creds: Annotated[HTTPAuthorizationCredentials | None, Depends(_bearer_scheme)],
    ) -> None:
        # Actual verification is enforced uniformly by security_gate_middleware;
        # this dependency exposes bearerAuth in generated OpenAPI documentation.
        return None

    router = APIRouter(prefix="/api/v1")

    @router.get("/health", response_model=HealthResponse, tags=["System"])
    def get_health() -> HealthResponse:
        return runtime_service.health()

    @router.post(
        "/optimize",
        response_model=OptimizationResultWire,
        tags=["Optimization"],
        dependencies=[Depends(_require_bearer_doc)],
    )
    def post_optimize(body: OptimizationRequestWire) -> OptimizationResultWire:
        return runtime_service.optimize(body)

    @router.post(
        "/count",
        response_model=TokenCountResult,
        tags=["Optimization"],
        dependencies=[Depends(_require_bearer_doc)],
    )
    def post_count(body: TokenCountRequest) -> TokenCountResult:
        return runtime_service.count_tokens(body)

    @router.post(
        "/analyze",
        response_model=AnalyzeResponse,
        tags=["Optimization"],
        dependencies=[Depends(_require_bearer_doc)],
    )
    def post_analyze(body: AnalyzeRequest) -> AnalyzeResponse:
        return runtime_service.analyze(body)

    @router.post(
        "/context/select",
        response_model=ContextSelectResponse,
        tags=["Context"],
        dependencies=[Depends(_require_bearer_doc)],
    )
    def post_context_select(body: ContextSelectRequest) -> ContextSelectResponse:
        return runtime_service.select_context(body)

    @router.post(
        "/context/compress",
        response_model=OptimizationResultWire,
        tags=["Context"],
        dependencies=[Depends(_require_bearer_doc)],
    )
    def post_context_compress(body: ContextCompressRequest) -> OptimizationResultWire:
        return runtime_service.compress_context(body)

    @router.post(
        "/logs/compress",
        response_model=OptimizationResultWire,
        tags=["Context"],
        dependencies=[Depends(_require_bearer_doc)],
    )
    def post_logs_compress(body: LogCompressRequest) -> OptimizationResultWire:
        return runtime_service.compress_logs(body)

    @router.get(
        "/metrics",
        response_model=MetricsSummaryResponse,
        tags=["Observability"],
        dependencies=[Depends(_require_bearer_doc)],
    )
    def get_metrics(
        integration: IntegrationSource | None = Query(default=None),
        window_days: int = Query(default=30, ge=1, le=365),
    ) -> MetricsSummaryResponse:
        return runtime_service.metrics(integration=integration, window_days=window_days)

    @router.get(
        "/settings",
        response_model=RuntimeSettings,
        tags=["System"],
        dependencies=[Depends(_require_bearer_doc)],
    )
    def get_settings() -> RuntimeSettings:
        return runtime_service.get_settings()

    @router.put(
        "/settings",
        response_model=RuntimeSettings,
        tags=["System"],
        dependencies=[Depends(_require_bearer_doc)],
    )
    def put_settings(body: RuntimeSettingsUpdate) -> RuntimeSettings:
        return runtime_service.update_settings(body)

    @router.get(
        "/providers",
        response_model=ProvidersResponse,
        tags=["System"],
        dependencies=[Depends(_require_bearer_doc)],
    )
    def get_providers() -> ProvidersResponse:
        return runtime_service.providers()

    app.include_router(router)
    return app
