"""Versioned provider/model metadata, tokenizer resolver, and pricing registry."""

from __future__ import annotations

from dataclasses import dataclass

from project_t_contracts import ProviderCatalogEntry, ProviderModelInfo

from ..anthropic import AnthropicTokenizerAdapter
from ..google import GoogleTokenizerAdapter
from ..interfaces import GenericFallbackTokenizer, TokenizerAdapter
from ..openai import OpenAITokenizerAdapter


@dataclass(frozen=True, slots=True)
class ModelMetadata:
    """Versioned model capabilities and decoupled pricing metadata."""

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
            ),
            ModelMetadata(
                provider_id="openai",
                model_name="gpt-4o-mini",
                tokenizer_name="o200k_base",
                context_window=128000,
                supports_exact_local_count=True,
                pricing_version=DEFAULT_PRICING_VERSION,
            ),
            ModelMetadata(
                provider_id="openai",
                model_name="gpt-4.1",
                tokenizer_name="o200k_base",
                context_window=1047576,
                supports_exact_local_count=True,
                pricing_version=DEFAULT_PRICING_VERSION,
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
            ),
        ),
    ),
)


class ProviderRegistry:
    """Resolves providers/models to tokenizer adapters and catalog metadata."""

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
            if m.model_name == model:
                return m
        return None

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
