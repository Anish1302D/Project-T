# ADR-0010: Browser Permissions and Supported Website Adapter Strategy

- **Status:** Accepted
- **Date:** 2026-11-18
- **Review Date:** 2027-03-01
- **Owners:** Project T Architecture
- **Related Master Doc Sections:** Sections 2, 9.1, 14, 17, 22

---

## Context

Users interact heavily with web-based AI interfaces (ChatGPT, Claude, Gemini). A browser extension can help them reduce unnecessary tokens before submitting long prompts, pasted logs, or multi-constraint instructions.

However:
1. Web AI UIs frequently change their DOM structures (`contenteditable`, `textarea`, ProseMirror/Slate editors).
2. Requesting broad `<all_urls>` host permissions or silently intercepting `fetch`/`XHR` network traffic introduces severe Chrome Web Store review issues, brittle internal API coupling, and serious privacy concerns (collecting unrelated pages, cookies, passwords, or private conversation threads).

## Decision

1. **Chrome Manifest V3 & Minimal Host Permissions:**
   - Build `apps/browser-extension` using TypeScript, React, and **Chrome Manifest V3**.
   - Request permissions strictly limited to explicitly supported AI site origins (ChatGPT, Claude, Gemini) plus `127.0.0.1` for authenticated Local Runtime communication. **Do not request `<all_urls>`**, `cookies`, or broad tab-reading permissions.
2. **Explicit User-Triggered DOM Extraction (No Silent Network Interception):**
   - Operate strictly on text in the active prompt input field upon explicit user action (button click, keyboard shortcut, or context menu action).
   - Never capture passwords, cookies, unrelated page content, or hidden background conversation requests.
3. **Common Site Adapter Interface (`integrations/`):**
   - Isolate site-specific DOM detection, text extraction, and text injection behind a unified `SiteAdapter` interface (per-site modules for ChatGPT, Claude, Gemini) so DOM changes on one site do not impact the extension core or other sites.
4. **Mandatory Review & Reversible Controls:**
   - Display original vs. optimized text diff, token estimate (`exact`/`estimated`), and reduction percentage in a lightweight review overlay/popup.
   - Require user acceptance before replacing the prompt field, and always retain a one-click **Reject / Restore Original** path before submission.
5. **Zero Secrets in Extension Bundle:**
   - Never ship provider API keys inside browser extension code or `chrome.storage`. Only store the user-configured Local Runtime connection settings/pairing token safely within extension storage.

## Alternatives Considered

### Option A: Intercept web app `fetch`/`XMLHttpRequest` network payloads in background/content script
- **Pros:** Could inspect full conversation history sent to ChatGPT/Claude/Gemini web backends.
- **Cons:** Extremely fragile across provider frontend updates, violates site integration boundaries, risks breaking encrypted/streaming web payloads, and requires invasive page-script injection.
- **Why rejected:** Explicitly rejected by Section 2 ("must not assume access to private internal platform requests or hidden conversation context") and Section 9.1.

### Option B: Broad `<all_urls>` permission so extension works on arbitrary textareas everywhere
- **Pros:** Works on any web form or internal company LLM playground automatically.
- **Cons:** Severe privacy footprint, fails principle of least privilege, triggers strict Chrome Web Store security scrutiny.
- **Why rejected:** Violates Section 9.1 ("Keep permissions restricted to supported sites") and Section 17 ("Minimal host permissions"). Custom self-hosted web URLs can be supported later via Manifest V3 `optional_host_permissions` with explicit user grant.

## Consequences

### Positive
- Strong user privacy posture and streamlined Manifest V3 permission review.
- Clean adapter abstraction allows rapid hotfixes when ChatGPT, Claude, or Gemini updates editor DOM markup.
- Users stay in control with transparent before/after preview and instant restore.

### Negative / Trade-offs
- Browser extension optimizes only the user's current draft prompt (not hidden system prompts or prior multi-turn chat history maintained server-side by the web UI).
- Site-specific DOM adapters require ongoing E2E smoke tests (Playwright/fixtures) as AI web UIs evolve.

### Risks & Mitigations
- **Risk:** React/ProseMirror controlled inputs ignore naive `.value = ...` assignments.
  - **Mitigation:** Implement adapter-specific input event/clipboard/selection replacement helpers and graceful fallback (copy-to-clipboard + manual paste notification) if DOM injection fails.

## Review Triggers

- Review on **2027-03-01** during Week 7 Browser Integration (`apps/browser-extension`) testing against live ChatGPT, Claude, and Gemini web interfaces.
