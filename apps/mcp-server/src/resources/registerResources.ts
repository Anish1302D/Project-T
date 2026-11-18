import type { McpServer } from "@modelcontextprotocol/sdk/server/mcp.js";
import type { McpRuntimeClient } from "../runtimeClient.js";

export function registerProjectTResources(server: McpServer, client: McpRuntimeClient): void {
  server.registerResource(
    "metrics-summary",
    "project-t://metrics/summary",
    {
      title: "Project T Optimization Metrics Summary",
      description: "Metadata-only 30-day token savings and fallback statistics from Local Runtime.",
      mimeType: "application/json"
    },
    async (uri) => {
      const metrics = await client.metrics(undefined, 30);
      return {
        contents: [
          {
            uri: uri.href,
            mimeType: "application/json",
            text: JSON.stringify(metrics, null, 2)
          }
        ]
      };
    }
  );

  server.registerResource(
    "runtime-settings",
    "project-t://settings/current",
    {
      title: "Project T Local Runtime Settings",
      description: "Current optimization mode, privacy defaults, and retention configuration.",
      mimeType: "application/json"
    },
    async (uri) => {
      const settings = await client.getSettings();
      return {
        contents: [
          {
            uri: uri.href,
            mimeType: "application/json",
            text: JSON.stringify(settings, null, 2)
          }
        ]
      };
    }
  );

  server.registerResource(
    "provider-catalog",
    "project-t://providers/catalog",
    {
      title: "Project T Provider & Tokenizer Catalog",
      description: "Registered providers, model metadata, local exact-count support, and pricing versions.",
      mimeType: "application/json"
    },
    async (uri) => {
      const providers = await client.providers();
      return {
        contents: [
          {
            uri: uri.href,
            mimeType: "application/json",
            text: JSON.stringify(providers, null, 2)
          }
        ]
      };
    }
  );
}
