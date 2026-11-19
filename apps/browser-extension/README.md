# Project T Browser Extension (`@project-t/browser-extension`)

Chrome Manifest V3 extension providing user-triggered prompt optimization and token preview on supported AI web interfaces (**ChatGPT**, **Claude**, and **Gemini**).

## Scope & Privacy Guarantees (`ADR-0010`)

- **Minimal host permissions:** Restricted strictly to `chatgpt.com`, `chat.openai.com`, `claude.ai`, `gemini.google.com`, and loopback `127.0.0.1:4765` / `localhost:4765` (no `<all_urls>`, no `cookies`, no background page scraping).
- **Explicit user trigger only:** Reads only the active prompt input field when you click **Optimize Prompt** (or trigger via popup), displays original vs. optimized text with token reduction % and `"Exact"` / `"Estimated"` badge, and requires explicit **Accept**, **Reject**, or **Restore Original** control.
- **Zero provider secrets in bundle:** Never stores OpenAI, Anthropic, or Google API keys in extension code or `chrome.storage`. Only stores Local Runtime pairing settings (`runtimeUrl`, local installation bearer token, and optimization mode).
- **Honest integration boundary:** Optimizes the active draft prompt in your editor before submission; does **not** claim access to hidden system prompts or server-side multi-turn history.
