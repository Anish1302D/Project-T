# Project T API Gateway (`project-t-api-gateway`)

FastAPI proxy gateway that normalizes and optimizes compatible OpenAI, Anthropic, and Google Gemini API requests routed through it before forwarding upstream, with streaming pass-through and provider usage reconciliation.

## Supported Routes

- `POST /v1/chat/completions` — OpenAI-compatible Chat Completions proxy
- `POST /v1/messages` — Anthropic Messages proxy
- `POST /v1beta/models/{model}:generateContent` — Google Gemini proxy
- `POST /v1beta/models/{model}:streamGenerateContent` — Google Gemini streaming proxy
- `GET /gateway/usage` — Metadata-only reconciled token and cost summary
- `GET /health` — Gateway liveness & SQLite readiness

## Controls & Guarantees

- **Bypass mode:** Send `X-ProjectT-Bypass: true` to forward the exact original request unmodified.
- **Fail-open fallback:** Optimization errors, timeouts, or validation failures forward the unmodified original payload upstream.
- **Structural invariance:** `tools`, `functions`, `tool_choice`, `tool_calls`, `tool_use`, `tool_result`, `response_format`, and `responseSchema` are never silently altered.
- **Honest accounting:** Separates pre-flight `exact`/`estimated` counts from `provider_confirmed_input_tokens` and versioned `cost_metrics`.
- **Routing boundary:** Only requests explicitly routed through the gateway are optimized.
