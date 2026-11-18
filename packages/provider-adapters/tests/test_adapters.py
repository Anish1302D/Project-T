"""Unit tests for provider adapters, accuracy labeling, and registry decoupling."""

from project_t_contracts import AccuracyLevel

from project_t_provider_adapters import (
    AnthropicTokenizerAdapter,
    GenericFallbackTokenizer,
    GoogleTokenizerAdapter,
    ModelRequest,
    OpenAITokenizerAdapter,
    ProviderRegistry,
    TokenizerAdapter,
)


def test_openai_adapter_labels_exact_for_known_models_and_estimated_otherwise() -> None:
    adapter = OpenAITokenizerAdapter(allow_tiktoken=True)
    assert isinstance(adapter, TokenizerAdapter)

    known = adapter.count_text("Fix the JWT middleware without changing schema.", "gpt-4o")
    assert known.provider == "openai"
    assert known.accuracy == AccuracyLevel.EXACT
    assert known.count > 0

    unknown = adapter.count_text("Fix the JWT middleware without changing schema.", "example-model")
    assert unknown.accuracy == AccuracyLevel.ESTIMATED
    assert unknown.count > 0

    offline = OpenAITokenizerAdapter(allow_tiktoken=False).count_text("Hello world", "gpt-4o")
    assert offline.accuracy == AccuracyLevel.ESTIMATED
    assert offline.count > 0

    req_count = adapter.count_request(
        ModelRequest(
            provider="openai",
            model="gpt-4o",
            system="You are helpful.",
            messages=[{"role": "user", "content": "Optimize prompt."}],
        )
    )
    assert req_count.accuracy == AccuracyLevel.ESTIMATED
    assert req_count.count > 0


def test_non_openai_and_generic_adapters_label_estimated_locally() -> None:
    for adapter, model in [
        (AnthropicTokenizerAdapter(), "claude-sonnet-4"),
        (GoogleTokenizerAdapter(), "gemini-2.5-pro"),
        (GenericFallbackTokenizer(), "generic"),
    ]:
        res = adapter.count_text("Check login API error trace.", model)
        assert res.accuracy == AccuracyLevel.ESTIMATED
        assert res.count > 0


def test_provider_registry_resolves_adapters_and_exposes_catalog() -> None:
    registry = ProviderRegistry()
    assert isinstance(registry.resolve_tokenizer("openai"), OpenAITokenizerAdapter)
    assert isinstance(registry.resolve_tokenizer("anthropic"), AnthropicTokenizerAdapter)
    assert isinstance(registry.resolve_tokenizer("google"), GoogleTokenizerAdapter)
    assert isinstance(registry.resolve_tokenizer("unknown-provider"), GenericFallbackTokenizer)

    catalog = registry.list_catalog_entries()
    provider_ids = [p.id for p in catalog]
    assert provider_ids == ["local", "openai", "anthropic", "google"]
    meta = registry.get_model_metadata("openai", "gpt-4o")
    assert meta is not None
    assert meta.supports_exact_local_count is True
    assert meta.pricing_version
