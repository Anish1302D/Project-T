"""Usage reconciliation and versioned cost_metrics recorder for API Gateway."""

from __future__ import annotations

from typing import Any

from project_t_contracts import AccuracyLevel
from project_t_local_runtime import LocalDatabase
from project_t_provider_adapters import (
    ProviderRegistry,
    extract_anthropic_usage,
    extract_google_usage,
    extract_openai_usage,
)

from ..providers import GatewayOptimizationOutcome


def extract_provider_usage(provider: str, response_json: dict[str, Any]) -> tuple[int | None, int | None]:
    if provider == "openai":
        return extract_openai_usage(response_json)
    if provider == "anthropic":
        return extract_anthropic_usage(response_json)
    if provider == "google":
        return extract_google_usage(response_json)
    return None, None


class UsageReconciler:
    """Reconciles pre-flight optimization estimates with provider-confirmed usage & pricing."""

    def __init__(
        self,
        *,
        db: LocalDatabase,
        registry: ProviderRegistry,
        installation_id: str,
    ) -> None:
        self._db = db
        self._registry = registry
        self._installation_id = installation_id

    def reconcile(
        self,
        *,
        outcome: GatewayOptimizationOutcome,
        provider_input_tokens: int | None,
        cached_input_tokens: int | None = None,
    ) -> str:
        run_id = self._db.record_optimization_run(
            installation_id=self._installation_id,
            integration="gateway",
            provider=outcome.provider,
            model=outcome.model,
            content_type="prompt",
            status=outcome.optimization_status,
            result=outcome.to_wire_summary(),
        )

        # Confirmed savings vs baseline can only be attributed exactly if pre-flight baseline was exact
        # (or reconciled in paired API benchmark evaluation).
        confirmed_saved: int | None = None
        if (
            provider_input_tokens is not None
            and outcome.accuracy == AccuracyLevel.EXACT
            and outcome.original_tokens > 0
        ):
            confirmed_saved = max(0, outcome.original_tokens - provider_input_tokens)

        cost = self._registry.calculate_cost_avoided(
            provider=outcome.provider,
            model=outcome.model,
            estimated_tokens_saved=outcome.tokens_saved,
            confirmed_tokens_saved=confirmed_saved,
            cached_tokens=cached_input_tokens or 0,
        )

        self._db.record_provider_usage(
            run_id=run_id,
            provider_confirmed_input_tokens=provider_input_tokens,
            pricing_version=cost.pricing_version if cost else None,
            estimated_cost_avoided_usd=cost.estimated_cost_avoided_usd if cost else 0.0,
            provider_confirmed_cost_avoided_usd=(
                cost.provider_confirmed_cost_avoided_usd if cost else None
            ),
        )
        return run_id

    def summary(self) -> dict[str, Any]:
        return self._db.query_gateway_summary()
