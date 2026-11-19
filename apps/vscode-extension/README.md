# Project T VS Code Extension (`@project-t/vscode-extension`)

Local-first token optimization, context analysis, workspace relevance ranking, and terminal output compression powered by Project T's authenticated Local Runtime (`http://127.0.0.1:4765/api/v1`).

## Features (MVP v0.2 / Release `v0.3.0`)

- **Optimize Selected Text:** Sends the current editor selection to `/api/v1/optimize`, opens a side-by-side before/after diff preview with token reduction and `"exact"` vs `"estimated"` badges, and requires explicit confirmation to apply (with one-click **Restore Last Original Text**).
- **Analyze Selected Prompt / Context:** Calls `/api/v1/analyze` to surface detected `ContentType`, extracted constraints, locked protected spans, and baseline token estimate.
- **Workspace File Relevance Analysis:** Calls `/api/v1/context/select` against an explicitly approved workspace folder to rank task-relevant files and tests via BM25/FTS5.
- **Compress Selected Terminal Output:** Captures user-selected terminal output (or explicit clipboard text) and compresses verbose logs via `/api/v1/logs/compress` while keeping original output recoverable.
- **Runtime Health & Metadata History Sidebar:** Displays Local Runtime liveness, aggregated metadata-only metrics (`/api/v1/metrics`), and session run summaries.
- **Secure Token Storage:** Stores the per-installation Local Runtime bearer token strictly in VS Code `SecretStorage` (never in plaintext `settings.json`).

## Scope & Limitations

- Operates **only** on content you explicitly select or workspaces you explicitly approve.
- Does **not** intercept, inspect, or rewrite internal model requests made by unrelated third-party AI extensions.
- Requires the Project T Local Runtime running locally on `127.0.0.1:4765` (by default) for optimization requests.
