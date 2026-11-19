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


def test_payload_serializers_preserve_tools_and_extract_usage() -> None:
    from project_t_contracts import ContentType
    from project_t_provider_adapters import (
        extract_anthropic_usage,
        extract_google_usage,
        extract_openai_usage,
        optimize_anthropic_payload,
        optimize_google_payload,
        optimize_openai_chat_payload,
    )

    def _shrink(text: str, _hint: ContentType | None) -> tuple[str, int, int]:
        return text.replace("Please kindly ", ""), 10, 4

    openai_req = {
        "model": "gpt-4o",
        "tools": [{"type": "function", "function": {"name": "search"}}],
        "tool_choice": "auto",
        "response_format": {"type": "json_object"},
        "messages": [
            {"role": "system", "content": "Please kindly obey schema."},
            {"role": "assistant", "content": None, "tool_calls": [{"id": "c1", "type": "function"}]},
            {"role": "tool", "tool_call_id": "c1", "content": "Please kindly keep tool output verbatim"},
            {"role": "user", "content": [{"type": "text", "text": "Please kindly summarize"}]},
        ],
    }
    o_out, o_orig, o_opt = optimize_openai_chat_payload(openai_req, _shrink)
    assert o_orig == 20 and o_opt == 8
    assert o_out["messages"][0]["content"] == "obey schema."
    assert o_out["messages"][1]["tool_calls"] == openai_req["messages"][1]["tool_calls"]
    assert o_out["messages"][2]["content"] == "Please kindly keep tool output verbatim"
    assert o_out["messages"][3]["content"][0]["text"] == "summarize"

    anthropic_req = {
        "model": "claude-sonnet-4",
        "system": [{"type": "text", "text": "Please kindly follow policy."}],
        "tools": [{"name": "get_weather", "input_schema": {"type": "object"}}],
        "messages": [
            {"role": "user", "content": [{"type": "text", "text": "Please kindly check NYC"}]},
            {"role": "assistant", "content": [{"type": "tool_use", "id": "tu_1", "name": "get_weather"}]},
            {"role": "user", "content": [{"type": "tool_result", "tool_use_id": "tu_1", "content": "Please kindly sunny"}]},
        ],
    }
    a_out, a_orig, a_opt = optimize_anthropic_payload(anthropic_req, _shrink)
    assert a_orig == 20 and a_opt == 8
    assert a_out["system"][0]["text"] == "follow policy."
    assert a_out["messages"][0]["content"][0]["text"] == "check NYC"
    assert a_out["messages"][2]["content"][0]["content"] == "Please kindly sunny"

    google_req = {
        "systemInstruction": {"parts": [{"text": "Please kindly stay concise."}]},
        "tools": [{"functionDeclarations": [{"name": "lookup"}]}],
        "generationConfig": {"responseSchema": {"type": "OBJECT"}},
        "contents": [
            {"role": "user", "parts": [{"text": "Please kindly run query"}]},
            {"role": "model", "parts": [{"functionCall": {"name": "lookup", "args": {}}}]},
            {"role": "user", "parts": [{"functionResponse": {"name": "lookup", "response": {"ok": True}}}]},
        ],
    }
    g_out, g_orig, g_opt = optimize_google_payload(google_req, _shrink)
    assert g_orig == 20 and g_opt == 8
    assert g_out["systemInstruction"]["parts"][0]["text"] == "stay concise."
    assert g_out["contents"][0]["parts"][0]["text"] == "run query"
    assert g_out["contents"][1]["parts"][0]["functionCall"]["name"] == "lookup"
    assert g_out["contents"][2]["parts"][0]["functionResponse"]["name"] == "lookup"

    assert extract_openai_usage({"usage": {"prompt_tokens": 120, "prompt_tokens_details": {"cached_tokens": 40}}}) == (120, 40)
    assert extract_anthropic_usage({"message": {"usage": {"input_tokens": 95, "cache_read_input_tokens": 15}}}) == (95, 15)
    assert extract_google_usage({"usageMetadata": {"promptTokenCount": 88, "cachedContentTokenCount": 12}}) == (88, 12)


def test_remote_token_counters_exact_and_offline_fallback() -> None:
    import asyncio
    import httpx

    anthropic_adapter = AnthropicTokenizerAdapter()
    google_adapter = GoogleTokenizerAdapter()

    def _ok_handler(request: httpx.Request) -> httpx.Response:
        if "count_tokens" in str(request.url):
            return httpx.Response(200, json={"input_tokens": 42})
        return httpx.Response(200, json={"totalTokens": 37})

    def _err_handler(_request: httpx.Request) -> httpx.Response:
        return httpx.Response(503, json={"error": "unavailable"})

    async def _run() -> None:
        async with httpx.AsyncClient(transport=httpx.MockTransport(_ok_handler)) as ok_client:
            a_exact = await anthropic_adapter.count_request_remote(
                ModelRequest(provider="anthropic", model="claude-sonnet-4", messages=[{"role": "user", "content": "Hello"}]),
                api_key="sk-ant-test",
                http_client=ok_client,
            )
            g_exact = await google_adapter.count_request_remote(
                ModelRequest(provider="google", model="gemini-2.5-pro", messages=[{"role": "user", "content": "Hello"}]),
                api_key="AIza-test",
                http_client=ok_client,
            )
        assert a_exact.accuracy == AccuracyLevel.EXACT and a_exact.count == 42
        assert g_exact.accuracy == AccuracyLevel.EXACT and g_exact.count == 37

        async with httpx.AsyncClient(transport=httpx.MockTransport(_err_handler)) as err_client:
            a_est = await anthropic_adapter.count_request_remote(
                ModelRequest(provider="anthropic", model="claude-sonnet-4", messages=[{"role": "user", "content": "Hello"}]),
                api_key="sk-ant-test",
                http_client=err_client,
            )
            g_est = await google_adapter.count_request_remote(
                ModelRequest(provider="google", model="gemini-2.5-pro", messages=[{"role": "user", "content": "Hello"}]),
                api_key="AIza-test",
                http_client=err_client,
            )
        assert a_est.accuracy == AccuracyLevel.ESTIMATED and a_est.count > 0
        assert g_est.accuracy == AccuracyLevel.ESTIMATED and g_est.count > 0

    asyncio.run(_run())


def test_registry_calculate_cost_avoided_and_prefix_matching() -> None:
    registry = ProviderRegistry()
    # Dated snapshot prefix should resolve to gpt-4o pricing
    snap = registry.get_model_metadata("openai", "gpt-4o-2026-01-01")
    assert snap is not None and snap.input_cost_per_1m_usd is not None and snap.input_cost_per_1m_usd > 0

    cost = registry.calculate_cost_avoided(
        provider="openai",
        model="gpt-4o",
        estimated_tokens_saved=100_000,
        confirmed_tokens_saved=80_000,
    )
    assert cost is not None
    assert cost.pricing_version
    assert cost.provider_confirmed_cost_avoided_usd is not None
    assert cost.estimated_cost_avoided_usd > cost.provider_confirmed_cost_avoided_usd > 0

    assert registry.calculate_cost_avoided(provider="local", model="heuristic", estimated_tokens_saved=100) is None
