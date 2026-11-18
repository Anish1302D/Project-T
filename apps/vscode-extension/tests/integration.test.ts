import { spawn, type ChildProcessWithoutNullStreams } from "node:child_process";
import * as fs from "node:fs";
import * as net from "node:net";
import * as os from "node:os";
import * as path from "node:path";
import { afterAll, beforeAll, describe, expect, it } from "vitest";
import {
  ExtensionCommandsController,
  type ExtensionHostAdapter
} from "../src/commands/handlers.js";
import { ReversibleOptimizationStore } from "../src/commands/state.js";
import { WorkspaceAllowlistStore, type MementoAdapter } from "../src/context/workspaceAllowlist.js";
import { LocalRuntimeClient } from "../src/runtime/client.js";
import { RuntimeTokenStore, type SecretStorageAdapter } from "../src/runtime/tokenStore.js";

function findFreePort(): Promise<number> {
  return new Promise((resolve, reject) => {
    const server = net.createServer();
    server.listen(0, "127.0.0.1", () => {
      const addr = server.address();
      if (!addr || typeof addr === "string") {
        server.close();
        reject(new Error("Could not allocate ephemeral port"));
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

async function waitForRuntimeHealth(url: string, timeoutMs = 15_000): Promise<void> {
  const started = Date.now();
  while (Date.now() - started < timeoutMs) {
    try {
      const res = await fetch(`${url}/health`);
      if (res.ok) {
        return;
      }
    } catch {
      // Wait for uvicorn startup
    }
    await new Promise((r) => setTimeout(r, 150));
  }
  throw new Error(`Timed out waiting for Local Runtime health at ${url}`);
}

describe("VS Code extension <-> Live Local Runtime integration", () => {
  const repoRoot = path.resolve(__dirname, "..", "..", "..");
  let tempDir: string;
  let workspaceDir: string;
  let dataDir: string;
  let serverProc: ChildProcessWithoutNullStreams | undefined;
  let baseUrl: string;
  let bearerToken: string;

  beforeAll(async () => {
    tempDir = fs.mkdtempSync(path.join(os.tmpdir(), "project-t-vscode-it-"));
    dataDir = path.join(tempDir, "runtime-data");
    workspaceDir = path.join(tempDir, "sample-workspace");
    fs.mkdirSync(path.join(workspaceDir, "src"), { recursive: true });
    fs.writeFileSync(
      path.join(workspaceDir, "src", "auth.py"),
      "def verify_jwt(token: str) -> bool:\n    return bool(token)\n",
      "utf-8"
    );

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

    await waitForRuntimeHealth(baseUrl);
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

  it("runs health, optimize, analyze, context select, terminal log compress, and restore against live FastAPI runtime", async () => {
    const secretMap = new Map<string, string>();
    const secrets: SecretStorageAdapter = {
      get: async (k) => secretMap.get(k),
      store: async (k, v) => {
        secretMap.set(k, v);
      },
      delete: async (k) => {
        secretMap.delete(k);
      }
    };
    const mementoMap = new Map<string, unknown>();
    const memento: MementoAdapter = {
      get: <T>(k: string, d: T) => (mementoMap.has(k) ? (mementoMap.get(k) as T) : d),
      update: async (k, v) => {
        mementoMap.set(k, v);
      }
    };

    const tokenStore = new RuntimeTokenStore(secrets);
    await tokenStore.setToken(bearerToken);
    const stateStore = new ReversibleOptimizationStore();
    const allowlist = new WorkspaceAllowlistStore(memento);
    const client = new LocalRuntimeClient({
      baseUrl,
      getToken: () => tokenStore.getToken()
    });

    const originalPrompt =
      "Hello, could you please inspect `verify_jwt` in src/auth.py in order to fix auth?\n\n" +
      "Repeated context paragraph detailing JWT signature rules.\n\n" +
      "Repeated context paragraph detailing JWT signature rules.\n\n" +
      "Do not change the database schema.";
    let editorBuffer = originalPrompt;
    let clipboardText = Array.from({ length: 20 }, (_, i) => `PASS tests/test_${i}.py`)
      .concat(["ValueError: invalid signature", "FAILED tests/test_auth.py", "1 failed, 20 passed"])
      .join("\n");

    const openedDocs: Array<{ title: string; content: string }> = [];

    const host: ExtensionHostAdapter = {
      getSettings: () => ({
        defaultMode: "balanced",
        defaultProvider: "local",
        defaultModel: "generic",
        preserveIdentifiers: true
      }),
      getActiveSelection: () => ({
        documentUri: "file:///prompt.md",
        selectedText: editorBuffer,
        startOffset: 0,
        endOffset: editorBuffer.length,
        languageId: "plaintext"
      }),
      replaceText: async (_uri, start, end, newText) => {
        editorBuffer = editorBuffer.slice(0, start) + newText + editorBuffer.slice(end);
        return true;
      },
      openDiffPreview: async () => undefined,
      openReadOnlyDocument: async (title, content) => {
        openedDocs.push({ title, content });
      },
      confirmOptimizationApply: async () => "apply",
      askInputBox: async () => "Fix verify_jwt signature",
      confirmWorkspaceApproval: async () => true,
      getActiveWorkspaceRoot: () => workspaceDir,
      terminalHost: {
        hasActiveTerminal: false,
        copySelection: async () => undefined,
        clipboard: {
          readText: async () => clipboardText,
          writeText: async (v) => {
            clipboardText = v;
          }
        }
      },
      showInfo: () => undefined,
      showWarning: () => undefined,
      showError: (msg) => {
        throw new Error(`Unexpected extension error: ${msg}`);
      }
    };

    const ctrl = new ExtensionCommandsController(client, tokenStore, stateStore, allowlist, host);

    expect(await ctrl.checkRuntimeHealth()).toBe(true);

    const optRes = await ctrl.optimizeSelection();
    expect(optRes?.validationPassed).toBe(true);
    expect(optRes?.tokensSaved).toBeGreaterThan(0);
    expect(editorBuffer).toContain("verify_jwt");
    expect(editorBuffer).toContain("Do not change the database schema.");
    expect(editorBuffer.length).toBeLessThan(originalPrompt.length);

    expect(await ctrl.restoreLastOriginal()).toBe(true);
    expect(editorBuffer).toBe(originalPrompt);

    const analysis = await ctrl.analyzeSelection();
    expect(analysis?.classification.mapped_content_type).toBe("developer_prompt");

    const contextSel = await ctrl.selectRelevantFiles();
    expect(contextSel?.selected_files.map((f) => f.relative_path)).toContain("src/auth.py");

    const termRes = await ctrl.compressTerminalOutput();
    expect(termRes?.tokensSaved).toBeGreaterThan(0);
    expect(clipboardText).toContain("ValueError: invalid signature");
    expect(openedDocs.length).toBeGreaterThanOrEqual(3);

    const metrics = await client.metrics(30);
    expect(metrics.total_runs).toBeGreaterThanOrEqual(2);
  }, 30_000);
});
