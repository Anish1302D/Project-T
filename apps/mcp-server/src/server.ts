import { McpServer } from "@modelcontextprotocol/sdk/server/mcp.js";
import { registerProjectTResources } from "./resources/registerResources.js";
import { McpRuntimeClient, type McpRuntimeClientOptions } from "./runtimeClient.js";
import { registerProjectTTools } from "./tools/registerTools.js";

export interface ProjectTMcpServerOptions {
  runtimeClient?: McpRuntimeClient;
  runtimeOptions?: McpRuntimeClientOptions;
  approvedWorkspaces?: readonly string[];
  version?: string;
}

export function createProjectTMcpServer(options: ProjectTMcpServerOptions = {}): McpServer {
  const client = options.runtimeClient ?? new McpRuntimeClient(options.runtimeOptions);
  const server = new McpServer({
    name: "project-t-mcp-server",
    version: options.version ?? "0.4.0"
  });

  registerProjectTTools(server, client, {
    approvedWorkspaces: options.approvedWorkspaces
  });
  registerProjectTResources(server, client);

  return server;
}
