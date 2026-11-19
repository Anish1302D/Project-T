"""Versioned provider/model metadata, tokenizer resolver, and decoupled pricing registry."""

from __future__ import annotations

from dataclasses import dataclass

from project_t_contracts import ProviderCatalogEntry, ProviderModelInfo

from ..anthropic import AnthropicTokenizerAdapter
from ..google import GoogleTokenizerAdapter
from ..interfaces import GenericFallbackTokenizer, TokenizerAdapter
from ..openai import OpenAITokenizerAdapter


@dataclass(frozen=True, slots=True)
class ModelMetadata:
    """Versioned model capabilities and decoupled pricing metadata (USD per 1M tokens)."""

    provider_id: str
    model_name: str
    tokenizer_name: str
    context_window: int
    supports_exact_local_count: bool
    pricing_version: str
    input_cost_per_1m_usd: float | None = None
    cached_input_cost_per_1m_usd: float | None = None
    output_cost_per_1m_usd: float | None = None


@dataclass(frozen=True, slots=True)
class ProviderMetadata:
    id: str
    display_name: str
    models: tuple[ModelMetadata, ...]


@dataclass(frozen=True, slots=True)
class CostAttribution:
    """Versioned cost avoided estimate/confirmed attribution."""

    pricing_version: str
    estimated_cost_avoided_usd: float
    provider_confirmed_cost_avoided_usd: float | None = None


DEFAULT_PRICING_VERSION = "2026-11-v1"

_DEFAULT_CATALOG: tuple[ProviderMetadata, ...] = (
    ProviderMetadata(
        id="local",
        display_name="Local Generic Estimator",
        models=(
            ModelMetadata(
                provider_id="local",
                model_name="generic",
                tokenizer_name="heuristic_char_lexical",
                context_window=128000,
                supports_exact_local_count=False,
                pricing_version=DEFAULT_PRICING_VERSION,
                input_cost_per_1m_usd=0.0,
                cached_input_cost_per_1m_usd=0.0,
                output_cost_per_1m_usd=0.0,
            ),
        ),
    ),
    ProviderMetadata(
        id="openai",
        display_name="OpenAI",
        models=(
            ModelMetadata(
                provider_id="openai",
                model_name="gpt-4o",
                tokenizer_name="o200k_base",
                context_window=128000,
                supports_exact_local_count=True,
                pricing_version=DEFAULT_PRICING_VERSION,
                input_cost_per_1m_usd=2.50,
                cached_input_cost_per_1m_usd=1.25,
                output_cost_per_1m_usd=10.00,
            ),
            ModelMetadata(
                provider_id="openai",
                model_name="gpt-4o-mini",
                tokenizer_name="o200k_base",
                context_window=128000,
                supports_exact_local_count=True,
                pricing_version=DEFAULT_PRICING_VERSION,
                input_cost_per_1m_usd=0.15,
                cached_input_cost_per_1m_usd=0.075,
                output_cost_per_1m_usd=0.60,
            ),
            ModelMetadata(
                provider_id="openai",
                model_name="gpt-4.1",
                tokenizer_name="o200k_base",
                context_window=1047576,
                supports_exact_local_count=True,
                pricing_version=DEFAULT_PRICING_VERSION,
                input_cost_per_1m_usd=2.00,
                cached_input_cost_per_1m_usd=0.50,
                output_cost_per_1m_usd=8.00,
            ),
        ),
    ),
    ProviderMetadata(
        id="anthropic",
        display_name="Anthropic",
        models=(
            ModelMetadata(
                provider_id="anthropic",
                model_name="claude-sonnet-4",
                tokenizer_name="anthropic_estimated_local",
                context_window=200000,
                supports_exact_local_count=False,
                pricing_version=DEFAULT_PRICING_VERSION,
                input_cost_per_1m_usd=3.00,
                cached_input_cost_per_1m_usd=0.30,
                output_cost_per_1m_usd=15.00,
            ),
        ),
    ),
    ProviderMetadata(
        id="google",
        display_name="Google Gemini",
        models=(
            ModelMetadata(
                provider_id="google",
                model_name="gemini-2.5-pro",
                tokenizer_name="gemini_estimated_local",
                context_window=1048576,
                supports_exact_local_count=False,
                pricing_version=DEFAULT_PRICING_VERSION,
                input_cost_per_1m_usd=1.25,
                cached_input_cost_per_1m_usd=0.3125,
                output_cost_per_1m_usd=10.00,
            ),
        ),
    ),
)


class ProviderRegistry:
    """Resolves providers/models to tokenizer adapters, catalog metadata, and cost attribution."""

    def __init__(
        self,
        catalog: tuple[ProviderMetadata, ...] = _DEFAULT_CATALOG,
        *,
        allow_tiktoken: bool = True,
    ) -> None:
        self._catalog = {p.id: p for p in catalog}
        self._adapters: dict[str, TokenizerAdapter] = {
            "openai": OpenAITokenizerAdapter(allow_tiktoken=allow_tiktoken),
            "anthropic": AnthropicTokenizerAdapter(),
            "google": GoogleTokenizerAdapter(),
            "local": GenericFallbackTokenizer(provider="local"),
        }

    def register_adapter(self, provider: str, adapter: TokenizerAdapter) -> None:
        self._adapters[provider.strip().lower()] = adapter

    def resolve_tokenizer(self, provider: str | None = None) -> TokenizerAdapter:
        key = (provider or "local").strip().lower()
        return self._adapters.get(key, GenericFallbackTokenizer(provider=key or "local"))

    def get_model_metadata(self, provider: str, model: str) -> ModelMetadata | None:
        entry = self._catalog.get(provider.strip().lower())
        if entry is None:
            return None
        for m in entry.models:
            if m.model_name == model or model.startswith(f"{m.model_name}-"):
                return m
        return None

    def calculate_cost_avoided(
        self,
        *,
        provider: str,
        model: str,
        estimated_tokens_saved: int,
        confirmed_tokens_saved: int | None = None,
        cached_tokens: int = 0,
    ) -> CostAttribution | None:
        """
        Compute versioned USD cost avoided from token savings without embedding pricing in engine core.

        Returns None when no pricing record is registered for (provider, model).
        """
        meta = self.get_model_metadata(provider, model)
        if meta is None or meta.input_cost_per_1m_usd is None:
            return None

        rate = meta.input_cost_per_1m_usd / 1_000_000.0
        cached_rate = (
            meta.cached_input_cost_per_1m_usd / 1_000_000.0
            if meta.cached_input_cost_per_1m_usd is not None
            else rate
        )

        # Conservative attribution: cached tokens save only at cached rate if applicable
        def _tokens_to_usd(saved: int) -> float:
            if saved <= 0:
                return 0.0
            if cached_tokens > 0:
                non_cached = max(0, saved - cached_tokens)
                cached_part = min(saved, cached_tokens)
                return round(non_cached * rate + cached_part * cached_rate, 8)
            return round(saved * rate, 8)

        est_usd = _tokens_to_usd(estimated_tokens_saved)
        conf_usd = (
            _tokens_to_usd(confirmed_tokens_saved)
            if confirmed_tokens_saved is not None
            else None
        )
        return CostAttribution(
            pricing_version=meta.pricing_version,
            estimated_cost_avoided_usd=est_usd,
            provider_confirmed_cost_avoided_usd=conf_usd,
        )

    def list_catalog_entries(self) -> list[ProviderCatalogEntry]:
        return [
            ProviderCatalogEntry(
                id=provider.id,
                display_name=provider.display_name,
                models=[
                    ProviderModelInfo(
                        model_name=model.model_name,
                        supports_exact_local_count=model.supports_exact_local_count,
                        pricing_version=model.pricing_version,
                    )
                    for model in provider.models
                ],
            )
            for provider in self._catalog.values()
        ]
