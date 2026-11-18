# ADR-0005: Tokenizer Adapter Interface and Exact/Estimated Labeling

- **Status:** Accepted
- **Date:** 2026-11-18
- **Review Date:** 2027-02-18
- **Owners:** Project T Architecture
- **Related Master Doc Sections:** Sections 3, 7.8, 8, 16, 21

---

## Context

Token counts differ materially across model providers and model families (e.g., OpenAI BPE variants vs Anthropic Claude tokenization vs Google Gemini tokenization). Furthermore, structured requests (system instructions, message arrays, tool definitions, JSON schemas) carry framing overhead that plain-text byte or word heuristics do not capture accurately.

Misrepresenting heuristic estimates as exact billable token counts—or presenting token reduction percentages directly as guaranteed cost savings without provider billing reconciliation—undermines user trust and platform credibility.

## Decision

1. **Provider-Agnostic `TokenizerAdapter` Interface:**
   - Define a uniform adapter interface in `packages/provider-adapters` (mirroring Section 8.1) supporting `countText(text, model)` and optional `countRequest(request)` for full structured payloads.
2. **Mandatory Accuracy Labeling (`"exact"` | `"estimated"`):**
   - Every `TokenCountResult` and optimization report must explicitly label whether counts are `"exact"` (produced by an authoritative model-specific tokenizer or provider counting endpoint) or `"estimated"` (produced by a heuristic fallback or non-authoritative local approximation).
   - Never promote `"estimated"` token counts as provider-confirmed savings.
3. **Initial Adapter Portfolio & Registry:**
   - Build a versioned **Provider Registry** mapping `(provider, model)` to the appropriate tokenizer adapter, request serializer, and versioned pricing metadata:
     - OpenAI adapter (local `tiktoken` / provider counting endpoint where available).
     - Anthropic adapter (provider message-counting endpoint where available; explicit local estimation fallback labeled `"estimated"`).
     - Google adapter (model-specific Gemini counting adapter / local fallback).
     - Generic fallback estimator for unknown/offline models, strictly labeled `"estimated"`.
4. **Decoupled Versioned Pricing:**
   - Keep pricing tables strictly separated from optimization algorithms in versioned registry data. Never hard-code pricing assumptions inside compression or selection logic.
5. **Offline Compatibility:**
   - Local optimization must continue working offline using local tokenizers or the generic estimator without blocking on external provider API calls.

## Alternatives Considered

### Option A: Single hardcoded tokenizer (e.g., `cl100k_base` or `chars / 4`) for all models
- **Pros:** Zero integration complexity; fast and offline.
- **Cons:** Produces materially inaccurate counts for newer OpenAI models, Claude models, Gemini models, and tool-use request payloads; violates Section 8 ("Do not build the platform around one tokenizer").
- **Why rejected:** Compromises accuracy and provider-aware accounting.

### Option B: Always call remote provider token-counting APIs for every optimization
- **Pros:** High counting accuracy before request submission.
- **Cons:** Breaks offline/local-first operation, adds network latency (>100 ms target violation), and risks exposing raw prompts to external provider endpoints when the user requested local-only processing.
- **Why rejected:** Violates local-first (Section 3.2) and privacy-by-default (Section 3.8) principles. Remote counting endpoints must be opt-in / used only when explicitly configured (such as API gateway preflight or explicit online counting).

## Consequences

### Positive
- Honest, auditable accounting separating `estimated`, `exact`, `provider-confirmed`, and `cost avoided`.
- Clean extensibility: adding a new provider or model requires only registering an adapter and metadata entry.
- Deterministic local pipeline meets latency goals (`< 100 ms`) without mandatory network round-trips.

### Negative / Trade-offs
- Offline Anthropic/Google counts may fall back to `"estimated"` unless local model-compatible tokenizers or explicit online provider counting calls are enabled.
- Requires ongoing maintenance of the versioned model/pricing registry as providers release new models.

### Risks & Mitigations
- **Risk:** Users confuse `"estimated"` savings in the UI with guaranteed bill reductions.
  - **Mitigation:** Display clear `"Estimated"` vs `"Exact"` / `"Provider-confirmed"` badges in extension UIs, MCP outputs, and dashboard analytics (Section 16).

## Review Triggers

- Review on **2027-02-18** or when integrating OpenAI/Anthropic/Google adapters in MVP v0.4.
