"""Integration tests for Project T API Gateway endpoints, invariance, streaming, and usage."""

from __future__ import annotations

import json
import logging
from pathlib import Path

import httpx
import pytest
from fastapi.testclient import TestClient

from project_t_api_gateway import GatewayConfig, create_gateway_app
from project_t_api_gateway.middleware import redacted_headers_snapshot


def _verbose_prompt(topic: str) -> str:
    return (
        f"Hello, could you please kindly help me with {topic} in order to improve reliability?\n\n"
        "Background note: Always keep database migrations backward compatible and never alter production schemas.\n\n"
        "Background note: Always keep database migrations backward compatible and never alter production schemas.\n\n"
        "Please make sure to return concise verified steps."
    )


def test_gateway_openai_anthropic_google_optimization_and_invariance(tmp_path: Path) -> None:
    captured_requests: list[tuple[str, dict[str, str], dict]] = []

    def _upstream_handler(request: httpx.Request) -> httpx.Response:
        body = json.loads(request.content.decode("utf-8"))
        captured_requests.append((str(request.url), dict(request.headers), body))
        url = str(request.url)
        if "/v1/chat/completions" in url:
            return httpx.Response(
                200,
                json={
                    "id": "chatcmpl_1",
                    "object": "chat.completion",
                    "usage": {
                        "prompt_tokens": 42,
                        "completion_tokens": 10,
                        "total_tokens": 52,
                        "prompt_tokens_details": {"cached_tokens": 12},
                    },
                    "choices": [{"index": 0, "message": {"role": "assistant", "content": "ok"}}],
                },
            )
        if "/v1/messages" in url:
            return httpx.Response(
                200,
                json={
                    "id": "msg_1",
                    "type": "message",
                    "usage": {"input_tokens": 39, "output_tokens": 9, "cache_read_input_tokens": 6},
                    "content": [{"type": "text", "text": "ok"}],
                },
            )
        return httpx.Response(
            200,
            json={
                "candidates": [{"content": {"parts": [{"text": "ok"}]}}],
                "usageMetadata": {"promptTokenCount": 35, "cachedContentTokenCount": 5},
            },
        )

    app = create_gateway_app(
        config=GatewayConfig(data_dir=tmp_path, db_path=tmp_path / "gw.db", allow_tiktoken=True),
        upstream_transport=httpx.MockTransport(_upstream_handler),
    )

    openai_tools = [{"type": "function", "function": {"name": "check_db", "parameters": {"type": "object"}}}]
    anthropic_tools = [{"name": "run_sql", "input_schema": {"type": "object"}}]
    google_schema = {"type": "OBJECT", "properties": {"status": {"type": "STRING"}}}

    with TestClient(app) as client:
        health = client.get("/health")
        assert health.status_code == 200
        assert health.json()["status"] == "ok"
        assert health.json()["sqlite_ready"] is True

        o_payload = {
            "model": "gpt-4o",
            "tools": openai_tools,
            "tool_choice": "auto",
            "response_format": {"type": "json_object"},
            "messages": [
                {"role": "system", "content": _verbose_prompt("JWT middleware")},
                {"role": "assistant", "content": None, "tool_calls": [{"id": "c1", "type": "function"}]},
                {"role": "tool", "tool_call_id": "c1", "content": "{\"row_count\": 4}"},
                {"role": "user", "content": _verbose_prompt("token rotation")},
            ],
        }
        o_resp = client.post(
            "/v1/chat/completions",
            json=o_payload,
            headers={"Authorization": "Bearer sk-test-openai-secret"},
        )
        assert o_resp.status_code == 200
        assert o_resp.headers["X-ProjectT-Status"] == "optimized"
        assert int(o_resp.headers["X-ProjectT-Tokens-Saved"]) > 0
        assert o_resp.headers["X-ProjectT-Accuracy"] == "exact"

        a_payload = {
            "model": "claude-sonnet-4",
            "system": _verbose_prompt("audit checks"),
            "tools": anthropic_tools,
            "tool_choice": {"type": "auto"},
            "messages": [
                {"role": "user", "content": _verbose_prompt("cache validation")},
                {"role": "assistant", "content": [{"type": "tool_use", "id": "tu_1", "name": "run_sql"}]},
                {"role": "user", "content": [{"type": "tool_result", "tool_use_id": "tu_1", "content": "rows=4"}]},
            ],
        }
        a_resp = client.post(
            "/v1/messages",
            json=a_payload,
            headers={"x-api-key": "sk-ant-test-secret", "anthropic-version": "2023-06-01"},
        )
        assert a_resp.status_code == 200
        assert a_resp.headers["X-ProjectT-Status"] == "optimized"
        assert int(a_resp.headers["X-ProjectT-Tokens-Saved"]) > 0

        g_payload = {
            "systemInstruction": {"parts": [{"text": _verbose_prompt("Gemini safety rules")}]},
            "tools": [{"functionDeclarations": [{"name": "inspect_index"}]}],
            "toolConfig": {"functionCallingConfig": {"mode": "AUTO"}},
            "generationConfig": {"responseMimeType": "application/json", "responseSchema": google_schema},
            "contents": [
                {"role": "user", "parts": [{"text": _verbose_prompt("FTS5 tokenization")}]},
                {"role": "model", "parts": [{"functionCall": {"name": "inspect_index", "args": {}}}]},
            ],
        }
        g_resp = client.post(
            "/v1beta/models/gemini-2.5-pro:generateContent",
            json=g_payload,
            headers={"x-goog-api-key": "AIzaTestGoogleSecret12345"},
        )
        assert g_resp.status_code == 200
        assert g_resp.headers["X-ProjectT-Status"] == "optimized"
        assert int(g_resp.headers["X-ProjectT-Tokens-Saved"]) > 0

        assert len(captured_requests) == 3
        _, o_hdrs, o_sent = captured_requests[0]
        assert o_hdrs["authorization"] == "Bearer sk-test-openai-secret"
        assert o_sent["tools"] == openai_tools
        assert o_sent["tool_choice"] == "auto"
        assert o_sent["response_format"] == {"type": "json_object"}
        assert o_sent["messages"][1] == o_payload["messages"][1]
        assert o_sent["messages"][2] == o_payload["messages"][2]

        _, a_hdrs, a_sent = captured_requests[1]
        assert a_hdrs["x-api-key"] == "sk-ant-test-secret"
        assert a_sent["tools"] == anthropic_tools
        assert a_sent["tool_choice"] == {"type": "auto"}
        assert a_sent["messages"][1] == a_payload["messages"][1]
        assert a_sent["messages"][2] == a_payload["messages"][2]

        _, g_hdrs, g_sent = captured_requests[2]
        assert g_hdrs["x-goog-api-key"] == "AIzaTestGoogleSecret12345"
        assert g_sent["tools"] == g_payload["tools"]
        assert g_sent["toolConfig"] == g_payload["toolConfig"]
        assert g_sent["generationConfig"] == g_payload["generationConfig"]
        assert g_sent["contents"][1] == g_payload["contents"][1]

        usage = client.get("/gateway/usage").json()
        assert usage["total_runs"] == 3
        assert usage["reconciled_runs"] == 3
        assert usage["total_provider_confirmed_input_tokens"] == 42 + 39 + 35
        assert usage["total_estimated_cost_avoided_usd"] > 0
        assert usage["total_confirmed_cost_avoided_usd"] > 0


def test_gateway_bypass_and_fail_open_fallback(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    forwarded_bodies: list[dict] = []

    def _handler(request: httpx.Request) -> httpx.Response:
        forwarded_bodies.append(json.loads(request.content.decode("utf-8")))
        return httpx.Response(200, json={"id": "ok", "usage": {"prompt_tokens": 50}})

    app = create_gateway_app(
        config=GatewayConfig(data_dir=tmp_path, db_path=tmp_path / "gw.db"),
        upstream_transport=httpx.MockTransport(_handler),
    )

    sample = {
        "model": "gpt-4o",
        "tools": [{"type": "function", "function": {"name": "ping"}}],
        "messages": [{"role": "user", "content": _verbose_prompt("bypass check")}],
    }

    with TestClient(app) as client:
        # 1. Explicit X-ProjectT-Bypass forwards body verbatim
        r_bypass = client.post(
            "/v1/chat/completions",
            json=sample,
            headers={"Authorization": "Bearer sk-bypass", "X-ProjectT-Bypass": "true"},
        )
        assert r_bypass.status_code == 200
        assert r_bypass.headers["X-ProjectT-Status"] == "bypassed"
        assert r_bypass.headers["X-ProjectT-Tokens-Saved"] == "0"
        assert forwarded_bodies[-1] == sample

        # 2. Mutating an invariant key inside optimizer triggers verify_provider_payload_invariance fail-open
        def _mutating_optimizer(payload: dict, _fn) -> tuple[dict, int, int]:
            bad = json.loads(json.dumps(payload))
            bad["tools"] = []  # Forbidden mutation!
            bad["messages"][0]["content"] = "short"
            return bad, 80, 10

        monkeypatch.setattr(
            "project_t_api_gateway.providers.normalizer.optimize_openai_chat_payload",
            _mutating_optimizer,
        )
        r_invariance = client.post(
            "/v1/chat/completions",
            json=sample,
            headers={"Authorization": "Bearer sk-inv"},
        )
        assert r_invariance.status_code == 200
        assert r_invariance.headers["X-ProjectT-Status"] == "fallback"
        assert forwarded_bodies[-1] == sample

        # 3. Unexpected exception inside optimizer also triggers fail-open unmodified forwarding
        def _exploding_optimizer(_payload: dict, _fn):
            raise RuntimeError("boom")

        monkeypatch.setattr(
            "project_t_api_gateway.providers.normalizer.optimize_openai_chat_payload",
            _exploding_optimizer,
        )
        r_err = client.post(
            "/v1/chat/completions",
            json=sample,
            headers={"Authorization": "Bearer sk-err"},
        )
        assert r_err.status_code == 200
        assert r_err.headers["X-ProjectT-Status"] == "fallback"
        assert forwarded_bodies[-1] == sample


def test_gateway_idempotency_key_retry_policy(tmp_path: Path) -> None:
    attempts: list[dict[str, str]] = []

    def _flaky_handler(request: httpx.Request) -> httpx.Response:
        attempts.append(dict(request.headers))
        if len(attempts) in (1, 3):
            raise httpx.ConnectError("transient network drop", request=request)
        return httpx.Response(200, json={"id": "ok", "usage": {"prompt_tokens": 12}})

    app = create_gateway_app(
        config=GatewayConfig(data_dir=tmp_path, db_path=tmp_path / "gw.db"),
        upstream_transport=httpx.MockTransport(_flaky_handler),
    )

    body = {"model": "gpt-4o", "messages": [{"role": "user", "content": "Hello"}]}

    with TestClient(app) as client:
        # Attempt 1 fails -> retries once because Idempotency-Key is set -> Attempt 2 succeeds
        r_retry = client.post(
            "/v1/chat/completions",
            json=body,
            headers={"Authorization": "Bearer sk-idem", "Idempotency-Key": "idem-xyz-001"},
        )
        assert r_retry.status_code == 200
        assert len(attempts) == 2
        assert attempts[0]["idempotency-key"] == "idem-xyz-001"
        assert attempts[1]["idempotency-key"] == "idem-xyz-001"

        # Attempt 3 fails -> NO retry when Idempotency-Key is absent
        r_no_retry = client.post(
            "/v1/chat/completions",
            json=body,
            headers={"Authorization": "Bearer sk-no-idem"},
        )
        assert r_no_retry.status_code == 502
        assert len(attempts) == 3


def test_gateway_sse_streaming_reconciliation_across_providers(tmp_path: Path) -> None:
    def _sse_handler(request: httpx.Request) -> httpx.Response:
        url = str(request.url)
        if "/v1/chat/completions" in url:
            stream_data = (
                b'data: {"choices":[{"delta":{"content":"Hi"}}]}\n\n'
                b'data: {"usage":{"prompt_tokens":55,"prompt_tokens_details":{"cached_tokens":10}}}\n\n'
                b"data: [DONE]\n\n"
            )
        elif "/v1/messages" in url:
            stream_data = (
                b"event: message_start\n"
                b'data: {"type":"message_start","message":{"usage":{"input_tokens":44,"cache_read_input_tokens":8}}}\n\n'
                b"event: message_stop\n"
                b'data: {"type":"message_stop"}\n\n'
            )
        else:
            stream_data = (
                b'data: {"candidates":[{"content":{"parts":[{"text":"Hi"}]}}],"usageMetadata":{"promptTokenCount":33}}\n\n'
            )
        return httpx.Response(200, content=stream_data, headers={"content-type": "text/event-stream"})

    app = create_gateway_app(
        config=GatewayConfig(data_dir=tmp_path, db_path=tmp_path / "gw.db"),
        upstream_transport=httpx.MockTransport(_sse_handler),
    )

    with TestClient(app) as client:
        r1 = client.post(
            "/v1/chat/completions",
            json={
                "model": "gpt-4o",
                "stream": True,
                "messages": [{"role": "user", "content": _verbose_prompt("stream openai")}],
            },
            headers={"Authorization": "Bearer sk-stream-o"},
        )
        assert r1.status_code == 200
        assert "[DONE]" in r1.text

        r2 = client.post(
            "/v1/messages",
            json={
                "model": "claude-sonnet-4",
                "stream": True,
                "messages": [{"role": "user", "content": _verbose_prompt("stream anthropic")}],
            },
            headers={"x-api-key": "sk-ant-stream"},
        )
        assert r2.status_code == 200
        assert "message_start" in r2.text

        r3 = client.post(
            "/v1beta/models/gemini-2.5-pro:streamGenerateContent?alt=sse",
            json={
                "contents": [{"role": "user", "parts": [{"text": _verbose_prompt("stream google")}]}],
            },
            headers={"x-goog-api-key": "AIzaStreamGoogle123456"},
        )
        assert r3.status_code == 200
        assert "promptTokenCount" in r3.text

        usage = client.get("/gateway/usage").json()
        assert usage["total_runs"] == 3
        assert usage["reconciled_runs"] == 3
        assert usage["total_provider_confirmed_input_tokens"] == 55 + 44 + 33


def test_gateway_secret_redaction_in_logs(
    tmp_path: Path, caplog: pytest.LogCaptureFixture
) -> None:
    def _failing_handler(request: httpx.Request) -> httpx.Response:
        raise httpx.ConnectError(f"failed with {request.headers.get('authorization')}", request=request)

    app = create_gateway_app(
        config=GatewayConfig(data_dir=tmp_path, db_path=tmp_path / "gw.db"),
        upstream_transport=httpx.MockTransport(_failing_handler),
    )

    snap = redacted_headers_snapshot(
        {
            "Authorization": "Bearer sk-secret-openai-999999",
            "x-api-key": "sk-ant-secret-999999",
            "x-goog-api-key": "AIzaSecretKey1234567890",
            "Idempotency-Key": "safe-idem-key",
        }
    )
    assert snap["Authorization"] == "[REDACTED]"
    assert snap["x-api-key"] == "[REDACTED]"
    assert snap["x-goog-api-key"] == "[REDACTED]"
    assert snap["Idempotency-Key"] == "safe-idem-key"

    with caplog.at_level(logging.WARNING):
        with TestClient(app) as client:
            client.post(
                "/v1/chat/completions",
                json={"model": "gpt-4o", "messages": [{"role": "user", "content": "SECRET_PROMPT_TEXT_XYZ"}]},
                headers={"Authorization": "Bearer sk-secret-openai-999999"},
            )

    assert "sk-secret-openai-999999" not in caplog.text
    assert "SECRET_PROMPT_TEXT_XYZ" not in caplog.text
