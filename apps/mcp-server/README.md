# Project T MCP Server (`@project-t/mcp-server`)

Model Context Protocol (MCP) server exposing Project T's local-first optimization tools and metadata resources to compatible MCP clients.

## Exposed Tools

| Tool | Local-Only? | Maps to | Input Limits |
|---|---|---|---|
| `optimize_prompt` | Yes (cloud only if AI semantic compression explicitly enabled) | `POST /api/v1/optimize` | 512 KB |
| `analyze_context` | Yes (`local-only`) | `POST /api/v1/analyze` | 512 KB |
| `compress_terminal_output` | Yes (`local-only`; no shell execution) | `POST /api/v1/logs/compress` | 1 MB |
| `select_relevant_files` | Yes (`local-only`; workspace-scoped) | `POST /api/v1/context/select` | Max 100 files |
| `deduplicate_context` | Yes (`local-only`) | `POST /api/v1/context/compress` | 100 items / 1 MB |
| `estimate_tokens` | Yes locally (optional remote if `allow_remote_count=true`) | `POST /api/v1/count` | 1 MB |
| `get_optimization_report` | Yes (`local-only`; metadata-only) | `GET /api/v1/metrics` | Read-only |

## Example VS Code `.vscode/mcp.json` Configuration

```json
{
  "servers": {
    "project-t": {
      "type": "stdio",
      "command": "node",
      "args": ["apps/mcp-server/dist/index.js"],
      "env": {
        "PROJECT_T_RUNTIME_URL": "http://127.0.0.1:4765/api/v1",
        "PROJECT_T_RUNTIME_TOKEN": "${input:projectTRuntimeToken}",
        "PROJECT_T_APPROVED_WORKSPACES": "${workspaceFolder}"
      }
    }
  }
}
```

## Boundaries & IDE Compatibility

- MCP tools run only when explicitly invoked by a compatible MCP host/client; MCP does **not** grant universal interception of an IDE's internal model traffic.
- Tested against the official `@modelcontextprotocol/sdk` client/server protocol and VS Code MCP schema conventions (`stdio` transport). Support for Cursor, Windsurf, or Antigravity extension/MCP interfaces must be validated directly against each host's live client before advertising support.
