"""Analytics HTTP endpoints serving aggregated multi-device views."""

from __future__ import annotations

from typing import Literal

from fastapi import APIRouter, Depends, Query

from ..authentication.router import get_current_principal
from ..authentication.tokens import AuthenticatedPrincipal
from ..config import CloudConfig
from ..storage import CloudDatabase
from .aggregator import compute_analytics_overview
from .cache import AnalyticsCache


def create_analytics_router(
    *,
    db: CloudDatabase,
    config: CloudConfig,
    cache: AnalyticsCache,
) -> APIRouter:
    router = APIRouter(prefix="/api/cloud/v1/analytics", tags=["Analytics"])

    @router.get("/overview")
    def get_overview(
        granularity: Literal["daily", "weekly", "monthly"] = Query(default="daily"),
        start_date: str | None = Query(default=None),
        end_date: str | None = Query(default=None),
        provider: str | None = Query(default=None),
        model: str | None = Query(default=None),
        integration: str | None = Query(default=None),
        mode: str | None = Query(default=None),
        accuracy: Literal["exact", "estimated"] | None = Query(default=None),
        device_id: str | None = Query(default=None),
        principal: AuthenticatedPrincipal = Depends(get_current_principal),
    ) -> dict[str, object]:
        cache_key = (
            f"analytics:{principal.user_id}:{granularity}:{start_date}:{end_date}:"
            f"{provider}:{model}:{integration}:{mode}:{accuracy}:{device_id}"
        )
        cached = cache.get_json(cache_key)
        if cached is not None:
            return cached

        rows = db.fetch_analytics_rows(
            user_id=principal.user_id,
            provider=provider,
            model=model,
            integration=integration,
            mode=mode,
            accuracy=accuracy,
            device_id=device_id,
        )
        benchmarks = db.fetch_benchmarks()
        devices = db.list_devices_for_user(principal.user_id)
        payload = compute_analytics_overview(
            rows=rows,
            benchmarks=benchmarks,
            devices=devices,
            granularity=granularity,
            start_date=start_date,
            end_date=end_date,
        )
        cache.set_json(cache_key, payload)
        return payload

    return router
