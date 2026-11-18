import * as fs from "node:fs";
import * as path from "node:path";
import { Client } from "@modelcontextprotocol/sdk/client/index.js";
import { InMemoryTransport } from "@modelcontextprotocol/sdk/inMemory.js";
import { describe, expect, it, vi } from "vitest";
import { McpRuntimeClient, McpRuntimeError } from "../src/runtimeClient.js";
import { createProjectTMcpServer } from "../src/server.js";
import {
  MAX_PROMPT_BYTES,
  validateWorkspaceAndPinnedPaths
} from "../src/tools/limits.js";

async function createConnectedTestPair(options: {
  fetchImpl?: typeof fetch;
  approvedWorkspaces?: string[];
}) {
  const clientApi = new McpRuntimeClient({
    token: "test-token",
    fetchImpl: options.fetchImpl ?? (vi.fn() as unknown as typeof fetch)
  });
  const server = createProjectTMcpServer({
    runtimeClient: clientApi,
    approvedWorkspaces: options.approvedWorkspaces
  });
  const client = new Client({ name: "test-mcp-client", version: "0.1.0" });
  const [clientTransport, serverTransport] = InMemoryTransport.createLinkedPair();
  await Promise.all([server.connect(serverTransport), client.connect(clientTransport)]);
  return { server, client };
}

describe("@project-t/mcp-server contract & security guards", () => {
  it("exposes all 7 typed tools with local-only disclosures and 3 resources", async () => {
    const { client, server } = await createConnectedTestPair({});
    try {
      const { tools } = await client.listTools();
      const names = tools.map((t) => t.name).sort();
      expect(names).toEqual([
        "analyze_context",
        "compress_terminal_output",
        "deduplicate_context",
        "estimate_tokens",
        "get_optimization_report",
        "optimize_prompt",
        "select_relevant_files"
      ]);

      for (const tool of tools) {
        expect(tool.description?.toLowerCase()).toContain("local-only");
        expect(tool.annotations?.destructiveHint).toBe(false);
      }

      const { resources } = await client.listResources();
      expect(resources.map((r) => r.uri).sort()).toEqual([
        "project-t://metrics/summary",
        "project-t://providers/catalog",
        "project-t://settings/current"
      ]);
    } finally {
      await Promise.all([client.close(), server.close()]);
    }
  });

  it("refuses non-loopback Local Runtime URLs by default", () => {
    expect(
      () => new McpRuntimeClient({ baseUrl: "http://0.0.0.0:4765/api/v1", token: "tok" })
    ).toThrowError(McpRuntimeError);
  });

  it("rejects unknown arguments and oversized payloads before calling Local Runtime", async () => {
    const mockFetch = vi.fn();
    const { client, server } = await createConnectedTestPair({
      fetchImpl: mockFetch as unknown as typeof fetch
    });
    try {
      // Unknown extra property fails strict Zod validation
      const extraFieldRes = await client.callTool({
        name: "optimize_prompt",
        arguments: { content: "hello", extra_malicious_arg: true }
      });
      expect(extraFieldRes.isError).toBe(true);
      expect(mockFetch).not.toHaveBeenCalled();

      // Oversized > 512 KB prompt rejected cleanly
      const oversized = "A".repeat(MAX_PROMPT_BYTES + 10);
      const bigRes = await client.callTool({
        name: "optimize_prompt",
        arguments: { content: oversized }
      });
      expect(bigRes.isError).toBe(true);
      expect(mockFetch).not.toHaveBeenCalled();

      // > 100 context items rejected
      const tooManyItems = Array.from({ length: 101 }, (_, i) => ({
        id: `item_${i}`,
        content: "x"
      }));
      const itemsRes = await client.callTool({
        name: "deduplicate_context",
        arguments: { items: tooManyItems }
      });
      expect(itemsRes.isError).toBe(true);
      expect(mockFetch).not.toHaveBeenCalled();
    } finally {
      await Promise.all([client.close(), server.close()]);
    }
  });

  it("blocks unapproved workspaces and pinned_files path traversal", () => {
    const approved = path.resolve("D:/Projects/ApprovedRepo");
    const outside = path.resolve("D:/Projects/OutsideRepo");

    expect(() => validateWorkspaceAndPinnedPaths(approved, [], [])).toThrow();
    expect(() => validateWorkspaceAndPinnedPaths(outside, [], [approved])).toThrow();
    expect(() =>
      validateWorkspaceAndPinnedPaths(approved, ["../../etc/passwd"], [approved])
    ).toThrow();
    expect(() =>
      validateWorkspaceAndPinnedPaths(approved, [path.resolve("D:/secret.txt")], [approved])
    ).toThrow();

    const ok = validateWorkspaceAndPinnedPaths(approved, ["src/auth.py"], [approved]);
    expect(ok.normalizedPinned).toEqual(["src/auth.py"]);
  });

  it("never imports child_process or shell execution utilities anywhere in src/", () => {
    const srcRoot = path.resolve(__dirname, "..", "src");
    const walk = (dir: string): string[] =>
      fs.readdirSync(dir, { withFileTypes: true }).flatMap((entry) => {
        const full = path.join(dir, entry.name);
        return entry.isDirectory() ? walk(full) : [full];
      });

    const tsFiles = walk(srcRoot).filter((f) => f.endsWith(".ts"));
    expect(tsFiles.length).toBeGreaterThan(0);

    for (const file of tsFiles) {
      const code = fs.readFileSync(file, "utf-8");
      expect(code).not.toMatch(/child_process/);
      expect(code).not.toMatch(/\bexecSync\b|\bspawnSync\b/);
    }
  });
});
