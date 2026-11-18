import { spawn, type ChildProcessWithoutNullStreams } from "node:child_process";
import * as fs from "node:fs";
import * as net from "node:net";
import * as os from "node:os";
import * as path from "node:path";
import { Client } from "@modelcontextprotocol/sdk/client/index.js";
import { InMemoryTransport } from "@modelcontextprotocol/sdk/inMemory.js";
import { afterAll, beforeAll, describe, expect, it } from "vitest";
import { createProjectTMcpServer } from "../src/server.js";

function findFreePort(): Promise<number> {
  return new Promise((resolve, reject) => {
    const server = net.createServer();
    server.listen(0, "127.0.0.1", () => {
      const addr = server.address();
      if (!addr || typeof addr === "string") {
        server.close();
        reject(new Error("Unable to allocate free loopback port"));
        return;
      }
      const { port } = addr;
      server.close(() => resolve(port));
    });
    server.on("error", reject);
  });
}

function resolvePythonExecutable(repoRoot: string): string {
  const winVenv = path.join(repoRoot, ".venv", "Scripts", "python.exe");
  if (fs.existsSync(winVenv)) {
    return winVenv;
  }
  const unixVenv = path.join(repoRoot, ".venv", "bin", "python");
  if (fs.existsSync(unixVenv)) {
    return unixVenv;
  }
  return process.env.PYTHON ?? "python";
}

async function waitForHealth(baseUrl: string, timeoutMs = 15_000): Promise<void> {
  const start = Date.now();
  while (Date.now() - start < timeoutMs) {
    try {
      const r = await fetch(`${baseUrl}/health`);
      if (r.ok) {
        return;
      }
    } catch {
      // Wait for uvicorn startup
    }
    await new Promise((r) => setTimeout(r, 150));
  }
  throw new Error(`Timed out waiting for Local Runtime at ${baseUrl}`);
}

describe("MCP Server <-> Live Local Runtime integration", () => {
  const repoRoot = path.resolve(__dirname, "..", "..", "..");
  let tempDir: string;
  let workspaceDir: string;
  let dataDir: string;
  let baseUrl: string;
  let bearerToken: string;
  let serverProc: ChildProcessWithoutNullStreams | undefined;

  beforeAll(async () => {
    tempDir = fs.mkdtempSync(path.join(os.tmpdir(), "project-t-mcp-it-"));
    dataDir = path.join(tempDir, "runtime-data");
    workspaceDir = path.join(tempDir, "workspace");
    fs.mkdirSync(path.join(workspaceDir, "src"), { recursive: true });
    fs.writeFileSync(
      path.join(workspaceDir, "src", "jwt.py"),
      "def verify_jwt_signature(token: str) -> bool:\n    return bool(token)\n",
      "utf-8"
    );
    fs.writeFileSync(path.join(workspaceDir, "README.md"), "# Workspace Notes\n", "utf-8");

    const port = await findFreePort();
    baseUrl = `http://127.0.0.1:${port}/api/v1`;
    const pyExe = resolvePythonExecutable(repoRoot);

    const bootstrapCode = `
import sys
import threading
from pathlib import Path
import uvicorn
from project_t_local_runtime import LocalRuntimeService, RuntimeConfig, create_app

cfg = RuntimeConfig(
    host="127.0.0.1",
    port=${port},
    data_dir=Path(r"${dataDir.replace(/\\/g, "\\\\")}"),
    approved_workspaces=(Path(r"${workspaceDir.replace(/\\/g, "\\\\")}"),),
    use_os_keyring=False,
    allow_tiktoken=False,
)
svc = LocalRuntimeService(config=cfg)
print(f"TOKEN_READY:{svc.credentials.bearer_token}", flush=True)
app = create_app(service=svc)
server = uvicorn.Server(uvicorn.Config(app, host="127.0.0.1", port=${port}, log_level="error"))

def _shutdown_on_stdin_eof():
    try:
        sys.stdin.read()
    finally:
        server.should_exit = True

threading.Thread(target=_shutdown_on_stdin_eof, daemon=True).start()
server.run()
`;

    serverProc = spawn(pyExe, ["-c", bootstrapCode], {
      cwd: repoRoot,
      env: {
        ...process.env,
        PYTHONPATH: [
          path.join(repoRoot, "packages", "contracts", "src"),
          path.join(repoRoot, "packages", "optimization-core", "src"),
          path.join(repoRoot, "packages", "provider-adapters", "src"),
          path.join(repoRoot, "apps", "local-runtime", "src")
        ].join(path.delimiter)
      }
    });

    bearerToken = await new Promise<string>((resolve, reject) => {
      const timer = setTimeout(() => reject(new Error("Timed out reading runtime token")), 15_000);
      let buffer = "";
      serverProc!.stdout.on("data", (chunk: Buffer) => {
        buffer += chunk.toString("utf-8");
        const match = buffer.match(/TOKEN_READY:([^\r\n]+)/);
        if (match?.[1]) {
          clearTimeout(timer);
          resolve(match[1].trim());
        }
      });
      serverProc!.stderr.on("data", (chunk: Buffer) => {
        buffer += chunk.toString("utf-8");
      });
      serverProc!.once("exit", (code) => {
        clearTimeout(timer);
        reject(new Error(`Local runtime exited early with code ${code}: ${buffer}`));
      });
    });

    await waitForHealth(baseUrl);
  }, 30_000);

  afterAll(async () => {
    if (serverProc && serverProc.exitCode === null) {
      await new Promise<void>((resolve) => {
        const timeout = setTimeout(() => {
          serverProc?.kill();
          resolve();
        }, 5000);
        serverProc!.once("exit", () => {
          clearTimeout(timeout);
          resolve();
        });
        serverProc!.stdin.end();
      });
    }
    if (tempDir && fs.existsSync(tempDir)) {
      fs.rmSync(tempDir, { recursive: true, force: true, maxRetries: 10, retryDelay: 100 });
    }
  });

  it("executes all 7 MCP tools and 3 metadata resources end-to-end against live FastAPI runtime", async () => {
    const mcpServer = createProjectTMcpServer({
      runtimeOptions: { baseUrl, token: bearerToken },
      approvedWorkspaces: [workspaceDir]
    });
    const mcpClient = new Client({ name: "e2e-mcp-client", version: "0.1.0" });
    const [clientTransport, serverTransport] = InMemoryTransport.createLinkedPair();
    await Promise.all([mcpServer.connect(serverTransport), mcpClient.connect(clientTransport)]);

    try {
      // 1. optimize_prompt
      const optRes = await mcpClient.callTool({
        name: "optimize_prompt",
        arguments: {
          content:
            "Hello, could you please inspect `verify_jwt_signature` in src/jwt.py in order to fix auth?\n\n" +
            "Repeated note explaining JWT verification rules across requests.\n\n" +
            "Repeated note explaining JWT verification rules across requests.\n\n" +
            "Do not change the database schema.",
          mode: "balanced"
        }
      });
      expect(optRes.isError).not.toBe(true);
      const optStructured = optRes.structuredContent as Record<string, any>;
      expect(optStructured.tokens.saved).toBeGreaterThan(0);
      expect(optStructured.optimized_content).toContain("verify_jwt_signature");
      expect(optStructured.optimized_content).toContain("Do not change the database schema.");

      // 2. analyze_context
      const anRes = await mcpClient.callTool({
        name: "analyze_context",
        arguments: {
          content: "Fix verify_jwt_signature in src/jwt.py. Do not modify schema."
        }
      });
      expect(anRes.isError).not.toBe(true);
      const anStructured = anRes.structuredContent as Record<string, any>;
      expect(anStructured.classification.mapped_content_type).toBe("developer_prompt");

      // 3. compress_terminal_output
      const noisyLog = Array.from({ length: 20 }, (_, i) => `PASS tests/unit/test_${i}.py`)
        .concat(["ValueError: expired jwt", "FAILED tests/test_jwt.py", "1 failed, 20 passed"])
        .join("\n");
      const logRes = await mcpClient.callTool({
        name: "compress_terminal_output",
        arguments: { output: noisyLog, command: "pytest", exit_code: 1 }
      });
      expect(logRes.isError).not.toBe(true);
      expect((logRes.structuredContent as Record<string, any>).tokens.saved).toBeGreaterThan(0);

      // 4. select_relevant_files (valid + traversal rejection)
      const selRes = await mcpClient.callTool({
        name: "select_relevant_files",
        arguments: {
          task_description: "Fix verify_jwt_signature",
          workspace_root: workspaceDir,
          pinned_files: ["README.md"]
        }
      });
      expect(selRes.isError).not.toBe(true);
      const selFiles = (selRes.structuredContent as Record<string, any>).selected_files as Array<{
        relative_path: string;
      }>;
      expect(selFiles.map((f) => f.relative_path)).toContain("src/jwt.py");

      const traversalRes = await mcpClient.callTool({
        name: "select_relevant_files",
        arguments: {
          task_description: "escape",
          workspace_root: workspaceDir,
          pinned_files: ["../outside.txt"]
        }
      });
      expect(traversalRes.isError).toBe(true);

      // 5. deduplicate_context
      const dedupRes = await mcpClient.callTool({
        name: "deduplicate_context",
        arguments: {
          items: [
            { id: "doc1", content: "Shared project rule about bearer authentication.", pinned: false },
            { id: "doc2", content: "Shared project rule about bearer authentication.", pinned: true }
          ],
          project_id: "proj_mcp"
        }
      });
      expect(dedupRes.isError).not.toBe(true);
      expect((dedupRes.structuredContent as Record<string, any>).tokens.saved).toBeGreaterThan(0);

      // 6. estimate_tokens
      const estRes = await mcpClient.callTool({
        name: "estimate_tokens",
        arguments: { text: "Check verify_jwt_signature", provider: "local", model: "generic" }
      });
      expect(estRes.isError).not.toBe(true);
      expect((estRes.structuredContent as Record<string, any>).accuracy).toBe("estimated");

      // 7. get_optimization_report
      const repRes = await mcpClient.callTool({
        name: "get_optimization_report",
        arguments: { window_days: 30 }
      });
      expect(repRes.isError).not.toBe(true);
      expect((repRes.structuredContent as Record<string, any>).total_runs).toBeGreaterThanOrEqual(2);

      // Resources check
      const metricsResource = await mcpClient.readResource({ uri: "project-t://metrics/summary" });
      expect(metricsResource.contents[0]?.text).toContain("total_runs");

      const settingsResource = await mcpClient.readResource({ uri: "project-t://settings/current" });
      expect(settingsResource.contents[0]?.text).toContain("cloud_sync_enabled");

      const providersResource = await mcpClient.readResource({ uri: "project-t://providers/catalog" });
      expect(providersResource.contents[0]?.text).toContain("openai");
    } finally {
      await Promise.all([mcpClient.close(), mcpServer.close()]);
    }
  }, 30_000);
});
