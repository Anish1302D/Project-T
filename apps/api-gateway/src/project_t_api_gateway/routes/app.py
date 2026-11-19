"""FastAPI API Gateway routes for OpenAI, Anthropic, and Google Gemini proxies."""

from __future__ import annotations

import json
import logging
from contextlib import asynccontextmanager
from typing import Any

import httpx
from fastapi import FastAPI, Request, Response
from fastapi.responses import JSONResponse, StreamingResponse
from project_t_contracts import OptimizationMode
from project_t_local_runtime import CredentialStore, LocalDatabase
from project_t_provider_adapters import ProviderRegistry

from ..config import GATEWAY_VERSION, GatewayConfig
from ..middleware import GatewayRedactingFilter, build_upstream_headers
from ..providers import GatewayOptimizer
from ..streaming import stream_upstream_sse
from ..usage import UsageReconciler, extract_provider_usage

logger = logging.getLogger("project_t.api_gateway")
if not any(isinstance(f, GatewayRedactingFilter) for f in logger.filters):
    logger.addFilter(GatewayRedactingFilter())


def _parse_bypass_header(headers: dict[str, str]) -> bool:
    val = headers.get("x-projectt-bypass", "").strip().lower()
    return val in {"1", "true", "yes"}


def _parse_mode_header(headers: dict[str, str]) -> OptimizationMode:
    raw = headers.get("x-projectt-mode", "balanced").strip().lower()
    if raw in {"safe", "balanced", "aggressive"}:
        return OptimizationMode(raw)
    return OptimizationMode.BALANCED


def create_gateway_app(
    *,
    config: GatewayConfig | None = None,
    upstream_transport: httpx.AsyncBaseTransport | None = None,
) -> FastAPI:
    """Create the Project T API Gateway FastAPI application."""
    gw_config = config if config is not None else GatewayConfig()
    registry = ProviderRegistry(allow_tiktoken=gw_config.allow_tiktoken)
    creds = CredentialStore(
        gw_config.data_dir,
        use_os_keyring=gw_config.use_os_keyring,
    ).load_or_create()
    db = LocalDatabase(gw_config.resolved_db_path)
    db.initialize(
        installation_id=creds.installation_id,
        runtime_version=GATEWAY_VERSION,
        registry=registry,
    )
    optimizer = GatewayOptimizer(registry=registry)
    reconciler = UsageReconciler(
        db=db,
        registry=registry,
        installation_id=creds.installation_id,
    )

    upstream_client = httpx.AsyncClient(
        transport=upstream_transport,
        timeout=gw_config.upstream_timeout_seconds,
    )

    @asynccontextmanager
    async def lifespan(_: FastAPI):
        try:
            yield
        finally:
            await upstream_client.aclose()
            db.close()

    app = FastAPI(
        title="Project T API Gateway",
        version=GATEWAY_VERSION,
        lifespan=lifespan,
    )
    app.state.gateway_db = db
    app.state.reconciler = reconciler

    async def _proxy_provider_request(
        *,
        request: Request,
        provider: str,
        upstream_url: str,
        default_model: str,
        is_stream_override: bool = False,
    ) -> Response:
        raw_body = await request.body()
        if len(raw_body) > gw_config.max_body_bytes:
            return JSONResponse(
                status_code=413,
                content={"error": {"code": "payload_too_large", "message": "Request exceeds gateway limit."}},
            )

        try:
            payload = json.loads(raw_body)
        except json.JSONDecodeError:
            return JSONResponse(
                status_code=400,
                content={"error": {"code": "invalid_json", "message": "Malformed JSON request body."}},
            )

        if not isinstance(payload, dict):
            return JSONResponse(
                status_code=400,
                content={"error": {"code": "invalid_request", "message": "JSON object body required."}},
            )

        lowered_headers = {k.lower(): v for k, v in request.headers.items()}
        bypass = _parse_bypass_header(lowered_headers)
        mode = _parse_mode_header(lowered_headers)
        model = str(payload.get("model") or default_model)
        is_stream = bool(payload.get("stream", False)) or is_stream_override

        outcome = optimizer.process(
            provider=provider,
            model=model,
            payload=payload,
            mode=mode,
            bypass=bypass,
        )

        forward_headers = build_upstream_headers(provider, dict(request.headers))
        gateway_meta_headers = {
            "X-ProjectT-Request-Id": outcome.request_id,
            "X-ProjectT-Status": outcome.gateway_status,
            "X-ProjectT-Accuracy": str(outcome.accuracy),
            "X-ProjectT-Tokens-Saved": str(outcome.tokens_saved),
        }

        if is_stream:
            async def _on_stream_done(
                in_tokens: int | None,
                cached_tokens: int | None,
            ) -> None:
                reconciler.reconcile(
                    outcome=outcome,
                    provider_input_tokens=in_tokens,
                    cached_input_tokens=cached_tokens,
                )

            try:
                status_code, resp_headers, byte_iter = await stream_upstream_sse(
                    client=upstream_client,
                    upstream_url=upstream_url,
                    headers=forward_headers,
                    json_body=outcome.payload_to_forward,
                    provider=provider,
                    on_complete=_on_stream_done,
                )
            except httpx.HTTPError as exc:
                logger.warning("Upstream stream transport failure (%s)", type(exc).__name__)
                return JSONResponse(
                    status_code=502,
                    content={"error": {"code": "upstream_unavailable", "message": "Upstream provider unreachable."}},
                    headers=gateway_meta_headers,
                )

            return StreamingResponse(
                byte_iter,
                status_code=status_code,
                media_type=resp_headers.get("content-type", "text/event-stream"),
                headers={**resp_headers, **gateway_meta_headers},
            )

        # Non-streaming JSON request: safe 1x retry on transient transport error ONLY when Idempotency-Key present
        max_attempts = 2 if "idempotency-key" in lowered_headers else 1
        upstream_resp: httpx.Response | None = None
        last_exc: Exception | None = None

        for _ in range(max_attempts):
            try:
                upstream_resp = await upstream_client.post(
                    upstream_url,
                    json=outcome.payload_to_forward,
                    headers=forward_headers,
                )
                break
            except httpx.TransportError as exc:
                last_exc = exc

        if upstream_resp is None:
            logger.warning("Upstream transport failure (%s)", type(last_exc).__name__)
            return JSONResponse(
                status_code=502,
                content={"error": {"code": "upstream_unavailable", "message": "Upstream provider unreachable."}},
                headers=gateway_meta_headers,
            )

        resp_content = upstream_resp.content
        resp_media = upstream_resp.headers.get("content-type", "application/json")
        if 200 <= upstream_resp.status_code < 300:
            try:
                resp_json: dict[str, Any] = upstream_resp.json()
                if isinstance(resp_json, dict):
                    in_tok, cached_tok = extract_provider_usage(provider, resp_json)
                    reconciler.reconcile(
                        outcome=outcome,
                        provider_input_tokens=in_tok,
                        cached_input_tokens=cached_tok,
                    )
            except Exception:
                reconciler.reconcile(outcome=outcome, provider_input_tokens=None)

        return Response(
            content=resp_content,
            status_code=upstream_resp.status_code,
            media_type=resp_media,
            headers=gateway_meta_headers,
        )

    @app.get("/health")
    def get_health() -> dict[str, object]:
        return {
            "status": "ok" if db.is_ready() else "degraded",
            "version": GATEWAY_VERSION,
            "sqlite_ready": db.is_ready(),
        }

    @app.get("/gateway/usage")
    def get_usage() -> dict[str, object]:
        return reconciler.summary()

    @app.post("/v1/chat/completions")
    async def proxy_openai_chat(request: Request) -> Response:
        upstream_url = f"{gw_config.openai_base_url.rstrip('/')}/v1/chat/completions"
        return await _proxy_provider_request(
            request=request,
            provider="openai",
            upstream_url=upstream_url,
            default_model="gpt-4o",
        )

    @app.post("/v1/messages")
    async def proxy_anthropic_messages(request: Request) -> Response:
        upstream_url = f"{gw_config.anthropic_base_url.rstrip('/')}/v1/messages"
        return await _proxy_provider_request(
            request=request,
            provider="anthropic",
            upstream_url=upstream_url,
            default_model="claude-sonnet-4",
        )

    @app.post("/v1beta/models/{model_action}")
    async def proxy_google_gemini(model_action: str, request: Request) -> Response:
        if model_action.endswith(":streamGenerateContent"):
            model = model_action[: -len(":streamGenerateContent")]
            is_stream = True
        elif model_action.endswith(":generateContent"):
            model = model_action[: -len(":generateContent")]
            is_stream = False
        else:
            return JSONResponse(
                status_code=404,
                content={"error": {"code": "unsupported_action", "message": "Unsupported Gemini model action."}},
            )

        query_str = f"?{request.url.query}" if request.url.query else ""
        upstream_url = f"{gw_config.google_base_url.rstrip('/')}/v1beta/models/{model_action}{query_str}"
        return await _proxy_provider_request(
            request=request,
            provider="google",
            upstream_url=upstream_url,
            default_model=model or "gemini-2.5-pro",
            is_stream_override=is_stream,
        )

    return app
