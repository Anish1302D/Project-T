#!/usr/bin/env node
import * as path from "node:path";
import { StdioServerTransport } from "@modelcontextprotocol/sdk/server/stdio.js";
import { createProjectTMcpServer } from "./server.js";

export { createProjectTMcpServer } from "./server.js";
export { McpRuntimeClient, McpRuntimeError, isLoopbackRuntimeUrl, resolveRuntimeToken } from "./runtimeClient.js";
export * from "./tools/limits.js";

async function runCli(): Promise<void> {
  const envWorkspaces = process.env.PROJECT_T_APPROVED_WORKSPACES
    ?.split(path.delimiter)
    .map((p) => p.trim())
    .filter(Boolean);

  const server = createProjectTMcpServer({
    approvedWorkspaces: envWorkspaces
  });

  const transport = new StdioServerTransport();
  await server.connect(transport);
}

// Only start stdio transport when invoked as CLI entrypoint.
const isDirectExecution =
  typeof process !== "undefined" &&
  Array.isArray(process.argv) &&
  process.argv[1] !== undefined &&
  (process.argv[1].endsWith("index.js") || process.argv[1].endsWith("index.ts"));

if (isDirectExecution) {
  runCli().catch((err) => {
    const msg = err instanceof Error ? err.message : String(err);
    process.stderr.write(`project-t-mcp fatal error: ${msg}\n`);
    process.exit(1);
  });
}
