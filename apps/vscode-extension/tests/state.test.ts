import * as path from "node:path";
import { describe, expect, it, vi } from "vitest";
import {
  ExtensionCommandsController,
  inferContentTypeFromLanguage,
  type ExtensionHostAdapter
} from "../src/commands/handlers.js";
import { ReversibleOptimizationStore } from "../src/commands/state.js";
import { WorkspaceAllowlistStore, type MementoAdapter } from "../src/context/workspaceAllowlist.js";
import { LocalRuntimeClient } from "../src/runtime/client.js";
import { RuntimeTokenStore, type SecretStorageAdapter } from "../src/runtime/tokenStore.js";
import { captureSelectedTerminalText } from "../src/terminal/terminalCapture.js";

function createMemorySecrets(): SecretStorageAdapter {
  const map = new Map<string, string>();
  return {
    get: async (k) => map.get(k),
    store: async (k, v) => {
      map.set(k, v);
    },
    delete: async (k) => {
      map.delete(k);
    }
  };
}

function createMemoryMemento(): MementoAdapter {
  const map = new Map<string, unknown>();
  return {
    get: <T>(key: string, defaultValue: T) =>
      map.has(key) ? (map.get(key) as T) : defaultValue,
    update: async (key: string, value: unknown) => {
      map.set(key, value);
    }
  };
}

describe("VS Code extension state, security stores, and command workflows", () => {
  it("stores and rotates bearer tokens in SecretStorage only", async () => {
    const store = new RuntimeTokenStore(createMemorySecrets());
    expect(await store.getToken()).toBeUndefined();
    await store.setToken("  tok_12345  ");
    expect(await store.getToken()).toBe("tok_12345");
    await store.clearToken();
    expect(await store.getToken()).toBeUndefined();
  });

  it("enforces explicit workspace folder approvals and rejects outside paths", async () => {
    const allowlist = new WorkspaceAllowlistStore(createMemoryMemento());
    const root = path.resolve("D:/Projects/SampleWorkspace");
    expect(allowlist.isApproved(root)).toBe(false);

    await allowlist.approve(root);
    expect(allowlist.isApproved(root)).toBe(true);
    expect(allowlist.isApproved(path.join(root, "sub"))).toBe(true);
    expect(allowlist.isApproved(path.resolve("D:/Projects/OtherRepo"))).toBe(false);

    await allowlist.revoke(root);
    expect(allowlist.isApproved(root)).toBe(false);
  });

  it("captures terminal selection while preserving previous clipboard contents", async () => {
    let clipboardText = "prior user clipboard";
    const captured = await captureSelectedTerminalText({
      hasActiveTerminal: true,
      copySelection: async () => {
        clipboardText = "Traceback: ValueError: broken jwt";
      },
      clipboard: {
        readText: async () => clipboardText,
        writeText: async (v) => {
          clipboardText = v;
        }
      }
    });

    expect(captured).toEqual({
      text: "Traceback: ValueError: broken jwt",
      source: "terminal_selection"
    });
    expect(clipboardText).toBe("prior user clipboard");
  });

  it("executes optimize -> diff preview -> apply -> restoreLastOriginal cleanly", async () => {
    let editorBuffer =
      "Hello, could you please fix `verifyJwtToken` in order to stop 401 errors?";
    let diffOpened = false;
    const infos: string[] = [];

    const mockFetch = vi.fn(async () => {
      return new Response(
        JSON.stringify({
          request_id: "req_opt_1",
          original_content: editorBuffer,
          optimized_content: "Fix `verifyJwtToken` to stop 401 errors?",
          tokens: {
            original: 22,
            optimized: 13,
            saved: 9,
            reduction_percentage: 40.91,
            accuracy: "estimated"
          },
          validation: {
            passed: true,
            constraints_preserved: true,
            identifiers_preserved: true,
            structure_preserved: true,
            quality_score: 0.99
          },
          optimization: {
            methods: ["rule_based_compression"],
            mode: "balanced"
          },
          duration_ms: 3,
          warnings: []
        }),
        { status: 200 }
      );
    });

    const tokenStore = new RuntimeTokenStore(createMemorySecrets());
    await tokenStore.setToken("tok_live");
    const stateStore = new ReversibleOptimizationStore();
    const allowlist = new WorkspaceAllowlistStore(createMemoryMemento());
    const client = new LocalRuntimeClient({
      getToken: () => tokenStore.getToken(),
      fetchImpl: mockFetch as unknown as typeof fetch
    });

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
        languageId: "markdown"
      }),
      replaceText: async (_uri, start, end, newText) => {
        editorBuffer = editorBuffer.slice(0, start) + newText + editorBuffer.slice(end);
        return true;
      },
      openDiffPreview: async () => {
        diffOpened = true;
      },
      openReadOnlyDocument: async () => undefined,
      confirmOptimizationApply: async () => "apply",
      askInputBox: async () => undefined,
      confirmWorkspaceApproval: async () => true,
      getActiveWorkspaceRoot: () => undefined,
      terminalHost: {
        hasActiveTerminal: false,
        copySelection: async () => undefined,
        clipboard: { readText: async () => "", writeText: async () => undefined }
      },
      showInfo: (m) => infos.push(m),
      showWarning: () => undefined,
      showError: () => undefined
    };

    const ctrl = new ExtensionCommandsController(client, tokenStore, stateStore, allowlist, host);
    await ctrl.optimizeSelection();

    expect(diffOpened).toBe(true);
    expect(editorBuffer).toBe("Fix `verifyJwtToken` to stop 401 errors?");
    expect(stateStore.getHistory()).toHaveLength(1);
    // Ensure metadata-only history entries do not store raw prompt text
    expect(JSON.stringify(stateStore.getHistory()[0])).not.toContain("verifyJwtToken");

    const restored = await ctrl.restoreLastOriginal();
    expect(restored).toBe(true);
    expect(editorBuffer).toBe(
      "Hello, could you please fix `verifyJwtToken` in order to stop 401 errors?"
    );
    expect(infos.some((m) => m.includes("Restored original text"))).toBe(true);
  });

  it("maps editor language IDs to canonical ContentTypes accurately", () => {
    expect(inferContentTypeFromLanguage("python")).toBe("source_code");
    expect(inferContentTypeFromLanguage("json")).toBe("json");
    expect(inferContentTypeFromLanguage("markdown")).toBe("documentation");
    expect(inferContentTypeFromLanguage("plaintext")).toBe("developer_prompt");
  });
});
