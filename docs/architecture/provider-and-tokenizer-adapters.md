# Tokenizer and Provider Adapter Architecture (`packages/provider-adapters`)

**Master Reference:** Sections 3.6, 8, 9.4, 16, and 22 of [token-optimization-platform-architecture.md](../token-optimization-platform-architecture.md).  
**Related ADR:** [ADR-0005](../decisions/ADR-0005-tokenizer-adapter-and-accuracy-labeling.md).

---

## 1. Rationale

A single global tokenizer cannot model modern AI workloads accurately:
- OpenAI, Anthropic, and Google models apply distinct tokenization schemes.
- Structured chat/tool-calling payloads (`messages[]`, `system`, `tools[]`, JSON response formats) incur structural framing token overhead that raw plain-text counting misses.
- Billing rules (cached input tokens, multimodal inputs, provider-specific prompt tokens) evolve independently of compression algorithms.

Therefore, `packages/provider-adapters` isolates all tokenization, request serialization, and model metadata behind stable interfaces.

---

## 2. Core Adapter Contract

Matching Section 8.1:

```typescript
export interface TokenizerAdapter {
  provider: string;

  countText(
    text: string,
    model: string
  ): Promise<TokenCountResult>;

  countRequest?(
    request: ModelRequest
  ): Promise<TokenCountResult>;
}

export interface TokenCountResult {
  count: number;
  accuracy: "exact" | "estimated";
  model: string;
  provider: string;
}
```

### Python Equivalent Contract
In Python (`packages/optimization-core` / `packages/provider-adapters`), the equivalent `Protocol` / abstract base class mirrors `count_text(text: str, model: str) -> TokenCountResult` and optional `count_request(request: ModelRequest) -> TokenCountResult` so the engine remains decoupled from concrete provider SDKs.

---

## 3. Initial Adapters & Directory Layout

```text
packages/provider-adapters/
├── openai/       # Local BPE tokenizer (e.g., tiktoken) + optional OpenAI count endpoint
├── anthropic/    # Anthropic message-counting endpoint + explicit local fallback estimator
├── google/       # Google Gemini token-counting adapter + local fallback estimator
└── registry/     # Versioned provider/model catalog, adapter resolver, and pricing tables
```

### Accuracy Rules per Adapter
| Adapter Mode | When Used | `accuracy` Value | Offline? |
|---|---|---|---|
| **OpenAI model-matched local tokenizer** | Known OpenAI model with matching local encoding | `"exact"` (or `"estimated"` if chat/tool framing approximated) | Yes |
| **Provider remote counting endpoint** | User explicitly opts into online counting or API gateway preflight | `"exact"` | No |
| **Local approximation / unknown model** | Offline Anthropic/Google text without local tokenizer, or unrecognized model | `"estimated"` | Yes |

> **Rule:** Never label an approximation or generic fallback count as `"exact"`, and never represent pre-flight `"exact"`/`"estimated"` counts as `"provider-confirmed"` post-billing savings.

---

## 4. Provider Registry & Versioned Pricing

The **Provider Registry** (`packages/provider-adapters/registry/`) resolves `(provider, model)` pairs to:

1. **Tokenizer adapter instance** (and fallback policy).
2. **Request serializer** (converting canonical normalized requests to OpenAI Responses/Chat, Anthropic Messages, or Google GenerateContent format).
3. **Model capabilities metadata** (context window size, tool-calling support, structured outputs support).
4. **Versioned pricing record** (effective date, input cost per 1M tokens, cached input cost, output cost).

### Architectural Constraint on Pricing
- Model pricing is stored **only** in versioned registry metadata / `models` and `cost_metrics` tables.
- Optimization algorithms in `packages/optimization-core` must **never** hardcode dollar prices or model-specific billing assumptions.
