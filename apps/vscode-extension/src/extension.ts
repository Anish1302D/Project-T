import type { OptimizationMode } from "@project-t/contracts";
import * as vscode from "vscode";
import {
  ExtensionCommandsController,
  type CommandSettings,
  type ExtensionHostAdapter
} from "./commands/handlers.js";
import { ReversibleOptimizationStore } from "./commands/state.js";
import { WorkspaceAllowlistStore } from "./context/workspaceAllowlist.js";
import { DIFF_SCHEME, DiffContentProvider } from "./providers/diffContentProvider.js";
import { DEFAULT_LOCAL_RUNTIME_URL, LocalRuntimeClient } from "./runtime/client.js";
import { RuntimeTokenStore } from "./runtime/tokenStore.js";
import { ProjectTSidebarProvider } from "./views/sidebarProvider.js";

function readSettings(): CommandSettings {
  const cfg = vscode.workspace.getConfiguration("projectT");
  return {
    defaultMode: cfg.get<OptimizationMode>("defaultMode", "balanced"),
    defaultProvider: cfg.get<string>("defaultProvider", "local"),
    defaultModel: cfg.get<string>("defaultModel", "generic"),
    preserveIdentifiers: cfg.get<boolean>("preserveIdentifiers", true)
  };
}

function readRuntimeUrl(): string {
  const cfg = vscode.workspace.getConfiguration("projectT");
  return cfg.get<string>("runtimeUrl", DEFAULT_LOCAL_RUNTIME_URL);
}

export function activate(context: vscode.ExtensionContext): void {
  const tokenStore = new RuntimeTokenStore(context.secrets);
  const stateStore = new ReversibleOptimizationStore();
  const workspaceAllowlist = new WorkspaceAllowlistStore(context.globalState);
  const diffProvider = new DiffContentProvider();
  const sidebarProvider = new ProjectTSidebarProvider();

  const statusBar = vscode.window.createStatusBarItem(vscode.StatusBarAlignment.Right, 100);
  statusBar.command = "projectT.checkRuntimeHealth";
  statusBar.text = "$(sparkle) Project T";
  statusBar.tooltip = "Project T Local Runtime Status";
  statusBar.show();

  const makeClient = (): LocalRuntimeClient =>
    new LocalRuntimeClient({
      baseUrl: readRuntimeUrl(),
      getToken: () => tokenStore.getToken()
    });

  const refreshViews = async (): Promise<void> => {
    const client = makeClient();
    let health = null;
    let healthError: string | undefined;
    let metrics = null;

    try {
      health = await client.health();
      statusBar.text = `$(sparkle) Project T: ${health.status === "ok" ? "Ready" : "Degraded"}`;
    } catch (err) {
      healthError = err instanceof Error ? err.message : String(err);
      statusBar.text = "$(warning) Project T: Offline";
    }

    try {
      metrics = await client.metrics(30);
    } catch {
      metrics = null;
    }

    sidebarProvider.updateSnapshot({
      health,
      healthError,
      metrics,
      history: stateStore.getHistory()
    });
  };

  const hostAdapter: ExtensionHostAdapter = {
    getSettings: readSettings,
    getActiveSelection: () => {
      const editor = vscode.window.activeTextEditor;
      if (!editor || editor.selection.isEmpty) {
        return null;
      }
      const startOffset = editor.document.offsetAt(editor.selection.start);
      const endOffset = editor.document.offsetAt(editor.selection.end);
      return {
        documentUri: editor.document.uri.toString(),
        selectedText: editor.document.getText(editor.selection),
        startOffset,
        endOffset,
        languageId: editor.document.languageId
      };
    },
    replaceText: async (documentUri, startOffset, endOffset, newText) => {
      const parsedUri = vscode.Uri.parse(documentUri);
      const doc = await vscode.workspace.openTextDocument(parsedUri);
      const editor = await vscode.window.showTextDocument(doc);
      const range = new vscode.Range(doc.positionAt(startOffset), doc.positionAt(endOffset));
      return editor.edit((editBuilder) => {
        editBuilder.replace(range, newText);
      });
    },
    openDiffPreview: async (requestId, originalText, optimizedText, title) => {
      const { originalUri, optimizedUri } = DiffContentProvider.makePairUris(requestId);
      diffProvider.setContent(originalUri, originalText);
      diffProvider.setContent(optimizedUri, optimizedText);
      await vscode.commands.executeCommand("vscode.diff", originalUri, optimizedUri, title);
    },
    openReadOnlyDocument: async (_title, content, language = "markdown") => {
      const doc = await vscode.workspace.openTextDocument({ content, language });
      await vscode.window.showTextDocument(doc, { preview: true });
    },
    confirmOptimizationApply: async (message) => {
      const choice = await vscode.window.showInformationMessage(
        message,
        { modal: false },
        "Apply Optimization",
        "Reject"
      );
      return choice === "Apply Optimization" ? "apply" : "reject";
    },
    askInputBox: (prompt, placeHolder, password = false) =>
      Promise.resolve(
        vscode.window.showInputBox({ prompt, placeHolder, password, ignoreFocusOut: true })
      ),
    confirmWorkspaceApproval: async (workspaceRoot) => {
      const choice = await vscode.window.showWarningMessage(
        `Allow Project T Local Runtime to index and rank files under '${workspaceRoot}'?`,
        { modal: true },
        "Approve Workspace"
      );
      return choice === "Approve Workspace";
    },
    getActiveWorkspaceRoot: () => vscode.workspace.workspaceFolders?.[0]?.uri.fsPath,
    terminalHost: {
      get hasActiveTerminal() {
        return vscode.window.activeTerminal !== undefined;
      },
      copySelection: () => vscode.commands.executeCommand("workbench.action.terminal.copySelection"),
      clipboard: vscode.env.clipboard
    },
    showInfo: (msg) => void vscode.window.showInformationMessage(msg),
    showWarning: (msg) => void vscode.window.showWarningMessage(msg),
    showError: (msg) => void vscode.window.showErrorMessage(msg),
    onStateChanged: refreshViews
  };

  const runWithController = async <T>(
    fn: (ctrl: ExtensionCommandsController) => Promise<T>
  ): Promise<T | undefined> => {
    try {
      const ctrl = new ExtensionCommandsController(
        makeClient(),
        tokenStore,
        stateStore,
        workspaceAllowlist,
        hostAdapter
      );
      return await fn(ctrl);
    } catch (err) {
      const msg = err instanceof Error ? err.message : String(err);
      void vscode.window.showErrorMessage(`Project T: ${msg}`);
      return undefined;
    }
  };

  context.subscriptions.push(
    statusBar,
    vscode.workspace.registerTextDocumentContentProvider(DIFF_SCHEME, diffProvider),
    vscode.window.registerTreeDataProvider("projectT.overview", sidebarProvider),
    vscode.commands.registerCommand("projectT.optimizeSelection", () =>
      runWithController((c) => c.optimizeSelection())
    ),
    vscode.commands.registerCommand("projectT.restoreLastOriginal", () =>
      runWithController((c) => c.restoreLastOriginal())
    ),
    vscode.commands.registerCommand("projectT.analyzeSelection", () =>
      runWithController((c) => c.analyzeSelection())
    ),
    vscode.commands.registerCommand("projectT.selectRelevantFiles", () =>
      runWithController((c) => c.selectRelevantFiles())
    ),
    vscode.commands.registerCommand("projectT.compressTerminalOutput", () =>
      runWithController((c) => c.compressTerminalOutput())
    ),
    vscode.commands.registerCommand("projectT.checkRuntimeHealth", () =>
      runWithController((c) => c.checkRuntimeHealth())
    ),
    vscode.commands.registerCommand("projectT.configureToken", () =>
      runWithController((c) => c.configureToken())
    ),
    vscode.commands.registerCommand("projectT.refreshSidebar", refreshViews)
  );

  void refreshViews();
}

export function deactivate(): void {
  // No persistent background servers owned directly by extension host.
}
