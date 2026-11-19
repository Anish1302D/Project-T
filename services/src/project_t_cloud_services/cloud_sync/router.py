"""Opt-in metadata-only cloud sync routes with strict privacy-boundary enforcement."""

from __future__ import annotations

from typing import Any

from fastapi import APIRouter, Depends, HTTPException, Query, Request, status
from pydantic import ValidationError

from ..analytics.cache import AnalyticsCache
from ..authentication.router import get_current_principal
from ..authentication.tokens import AuthenticatedPrincipal
from ..config import CloudConfig
from ..storage import CloudDatabase
from .schemas import SyncBenchmarksRequest, SyncRuleRequest, SyncRunsRequest
from .validator import SyncBoundaryViolationError, validate_no_sensitive_sync_data


def _verify_installation_access(
    *,
    db: CloudDatabase,
    principal: AuthenticatedPrincipal,
    installation_id: str,
) -> dict[str, Any]:
    if principal.token_scope == "sync" and principal.installation_id != installation_id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail={"error": {"code": "forbidden_installation", "message": "Sync token does not match installation."}},
        )
    inst = db.get_installation(installation_id)
    if inst is None or inst.get("user_id") != principal.user_id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail={"error": {"code": "unpaired_installation", "message": "Installation is not paired to your account."}},
        )
    if not bool(inst.get("sync_enabled")):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail={"error": {"code": "sync_disabled", "message": "Cloud sync is disabled for this installation."}},
        )
    return inst


async def _parse_and_check_boundary(request: Request) -> dict[str, Any]:
    try:
        raw_body = await request.json()
    except Exception as exc:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail={"error": {"code": "invalid_json", "message": "Malformed JSON payload."}},
        ) from exc

    if not isinstance(raw_body, dict):
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail={"error": {"code": "validation_error", "message": "Expected JSON object body."}},
        )

    try:
        validate_no_sensitive_sync_data(raw_body)
    except SyncBoundaryViolationError as exc:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail={"error": {"code": "sync_boundary_violation", "message": str(exc)}},
        ) from exc
    return raw_body


def create_sync_router(
    *,
    db: CloudDatabase,
    config: CloudConfig,
    cache: AnalyticsCache,
) -> APIRouter:
    router = APIRouter(prefix="/api/cloud/v1/sync", tags=["Cloud Sync"])

    @router.post("/runs")
    async def sync_runs(
        request: Request,
        principal: AuthenticatedPrincipal = Depends(get_current_principal),
    ) -> dict[str, object]:
        raw_body = await _parse_and_check_boundary(request)
        try:
            body = SyncRunsRequest.model_validate(raw_body)
        except ValidationError as exc:
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                detail={"error": {"code": "sync_boundary_violation", "message": "Unsupported or invalid metadata field."}},
            ) from exc

        inst = _verify_installation_access(
            db=db,
            principal=principal,
            installation_id=body.installation_id,
        )
        run_dicts = [
            {
                **r.model_dump(),
                "integration": str(r.integration),
                "content_type": str(r.content_type),
                "optimization_mode": str(r.optimization_mode),
                "status": str(r.status),
                "accuracy": str(r.accuracy),
            }
            for r in body.runs
        ]
        applied, received = db.upsert_synced_runs(
            installation_id=body.installation_id,
            device_id=inst.get("device_id"),
            runs=run_dicts,
        )
        cache.invalidate_user(principal.user_id)
        return {
            "installation_id": body.installation_id,
            "received": received,
            "upserted": applied,
            "metadata_only": True,
        }

    @router.post("/rules")
    async def sync_rule(
        request: Request,
        principal: AuthenticatedPrincipal = Depends(get_current_principal),
    ) -> dict[str, object]:
        raw_body = await _parse_and_check_boundary(request)
        try:
            body = SyncRuleRequest.model_validate(raw_body)
        except ValidationError as exc:
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                detail={"error": {"code": "sync_boundary_violation", "message": "Invalid rule payload."}},
            ) from exc

        _verify_installation_access(
            db=db,
            principal=principal,
            installation_id=body.installation_id,
        )
        res = db.sync_rule(
            rule_id=body.rule_id,
            installation_id=body.installation_id,
            project_id=body.project_id,
            scope=body.scope,
            mode=str(body.mode),
            preserve_identifiers=body.preserve_identifiers,
            allow_ai_semantic_compression=body.allow_ai_semantic_compression,
            min_meaningful_savings_tokens=body.min_meaningful_savings_tokens,
            rules=body.rules,
            version=body.version,
            prefer_local_override=body.prefer_local_override,
        )
        return res

    @router.get("/rules")
    def get_rules(
        installation_id: str = Query(..., min_length=3),
        principal: AuthenticatedPrincipal = Depends(get_current_principal),
    ) -> dict[str, object]:
        _verify_installation_access(
            db=db,
            principal=principal,
            installation_id=installation_id,
        )
        return {"installation_id": installation_id, "rules": db.list_rules(installation_id)}

    @router.post("/benchmarks")
    async def sync_benchmarks(
        request: Request,
        principal: AuthenticatedPrincipal = Depends(get_current_principal),
    ) -> dict[str, object]:
        raw_body = await _parse_and_check_boundary(request)
        try:
            body = SyncBenchmarksRequest.model_validate(raw_body)
        except ValidationError as exc:
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                detail={"error": {"code": "sync_boundary_violation", "message": "Invalid benchmark payload."}},
            ) from exc

        _verify_installation_access(
            db=db,
            principal=principal,
            installation_id=body.installation_id,
        )
        count = db.upsert_benchmark_results(
            [
                {**item.model_dump(), "optimization_mode": str(item.optimization_mode)}
                for item in body.results
            ]
        )
        cache.invalidate_user(principal.user_id)
        return {"upserted": count}

    return router
