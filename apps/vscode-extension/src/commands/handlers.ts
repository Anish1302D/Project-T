import type {
  AnalyzeResponseWire,
  ContentType,
  ContextSelectResponseWire,
  OptimizationMode,
  OptimizationResult
} from "@project-t/contracts";
import { buildPreviewViewModel } from "@project-t/shared-ui";
import type { WorkspaceAllowlistStore } from "../context/workspaceAllowlist.js";
import type { LocalRuntimeClient } from "../runtime/client.js";
import type { RuntimeTokenStore } from "../runtime/tokenStore.js";
import {
  captureSelectedTerminalText,
  type TerminalSelectionHost
} from "../terminal/terminalCapture.js";
import type { ReversibleOptimizationStore } from "./state.js";

export interface EditorSelectionTarget {
  documentUri: string;
  selectedText: string;
  startOffset: number;
  endOffset: number;
  languageId?: string;
}

export interface CommandSettings {
  defaultMode: OptimizationMode;
  defaultProvider: string;
  defaultModel: string;
  preserveIdentifiers: boolean;
}

export interface ExtensionHostAdapter {
  getSettings(): CommandSettings;
  getActiveSelection(): EditorSelectionTarget | null;
  replaceText(
    documentUri: string,
    startOffset: number,
    endOffset: number,
    newText: string
  ): Promise<boolean>;
  openDiffPreview(
    requestId: string,
    originalText: string,
    optimizedText: string,
    title: string
  ): Promise<void>;
  openReadOnlyDocument(title: string, content: string, language?: string): Promise<void>;
  confirmOptimizationApply(message: string): Promise<"apply" | "reject">;
  askInputBox(
    prompt: string,
    placeholder?: string,
    password?: boolean
  ): Thenable<string | undefined> | Promise<string | undefined>;
  confirmWorkspaceApproval(workspaceRoot: string): Promise<boolean>;
  getActiveWorkspaceRoot(): string | undefined;
  terminalHost: TerminalSelectionHost;
  showInfo(message: string): void;
  showWarning(message: string): void;
  showError(message: string): void;
  onStateChanged?(): Promise<void> | void;
}

export function inferContentTypeFromLanguage(languageId?: string): ContentType {
  if (!languageId) {
    return "developer_prompt";
  }
  const normalized = languageId.toLowerCase();
  if (normalized === "json" || normalized === "jsonc") {
    return "json";
  }
  if (normalized === "markdown") {
    return "documentation";
  }
  if (
    [
      "python",
      "typescript",
      "javascript",
      "typescriptreact",
      "javascriptreact",
      "rust",
      "go",
      "java",
      "sql"
    ].includes(normalized)
  ) {
    return "source_code";
  }
  return "developer_prompt";
}

export class ExtensionCommandsController {
  constructor(
    private readonly client: LocalRuntimeClient,
    private readonly tokenStore: RuntimeTokenStore,
    private readonly stateStore: ReversibleOptimizationStore,
    private readonly workspaceAllowlist: WorkspaceAllowlistStore,
    private readonly host: ExtensionHostAdapter
  ) {}

  async optimizeSelection(): Promise<OptimizationResult | null> {
    const selection = this.host.getActiveSelection();
    if (!selection || !selection.selectedText.trim()) {
      this.host.showWarning("Select text in the active editor before running Project T optimization.");
      return null;
    }

    const settings = this.host.getSettings();
    const contentType = inferContentTypeFromLanguage(selection.languageId);

    const { result } = await this.client.optimize({
      content: selection.selectedText,
      content_type: contentType,
      provider: settings.defaultProvider,
      model: settings.defaultModel,
      mode: settings.defaultMode,
      integration: "vscode",
      optimization: {
        deduplicate: true,
        semantic_compression: false,
        context_filtering: true,
        preserve_identifiers: settings.preserveIdentifiers
      }
    });

    this.stateStore.recordRun(result, "optimize_selection");
    await this.host.onStateChanged?.();

    const vm = buildPreviewViewModel(result);
    if (vm.fallbackTriggered || result.optimizedContent === selection.selectedText) {
      const reason = result.warnings[0] ?? "No meaningful token reduction";
      this.host.showInfo(
        `Project T kept original text unchanged (${vm.accuracyLabel}, reason: ${reason}).`
      );
      return result;
    }

    await this.host.openDiffPreview(
      result.requestId,
      result.originalContent,
      result.optimizedContent,
      `Project T Diff (${vm.reductionLabel} saved, ${vm.accuracyLabel})`
    );

    const choice = await this.host.confirmOptimizationApply(
      `Project T reduced tokens from ${vm.originalTokens} to ${vm.optimizedTokens} (-${vm.tokensSaved}, ${vm.reductionLabel}, ${vm.accuracyLabel}). Apply replacement?`
    );

    if (choice === "apply") {
      const applied = await this.host.replaceText(
        selection.documentUri,
        selection.startOffset,
        selection.startOffset + selection.selectedText.length,
        result.optimizedContent
      );
      if (applied) {
        this.stateStore.setLastAppliedEdit({
          requestId: result.requestId,
          documentUri: selection.documentUri,
          startOffset: selection.startOffset,
          endOffset: selection.startOffset + result.optimizedContent.length,
          originalText: result.originalContent,
          optimizedText: result.optimizedContent,
          appliedAtIso: new Date().toISOString()
        });
        this.host.showInfo(
          `Applied optimization (-${vm.tokensSaved} tokens, ${vm.accuracyLabel}). Use 'Restore Last Original Text' to undo.`
        );
      }
    } else {
      this.host.showInfo("Rejected optimization; original text retained.");
    }

    return result;
  }

  async restoreLastOriginal(): Promise<boolean> {
    const snapshot = this.stateStore.getLastAppliedEdit();
    if (!snapshot) {
      this.host.showWarning("No applied Project T optimization in this session to restore.");
      return false;
    }

    const restored = await this.host.replaceText(
      snapshot.documentUri,
      snapshot.startOffset,
      snapshot.endOffset,
      snapshot.originalText
    );
    if (restored) {
      this.stateStore.clearLastAppliedEdit();
      this.host.showInfo(`Restored original text for request ${snapshot.requestId}.`);
    }
    return restored;
  }

  async analyzeSelection(): Promise<AnalyzeResponseWire | null> {
    const selection = this.host.getActiveSelection();
    if (!selection || !selection.selectedText.trim()) {
      this.host.showWarning("Select prompt or code text in the editor to analyze.");
      return null;
    }

    const settings = this.host.getSettings();
    const analysis = await this.client.analyze({
      content: selection.selectedText,
      provider: settings.defaultProvider,
      model: settings.defaultModel
    });

    const reportLines = [
      "# Project T Context Analysis",
      "",
      `- **Mapped ContentType:** \`${analysis.classification.mapped_content_type}\` (subtype: \`${analysis.classification.type}\`)`,
      `- **Token Count:** \`${analysis.token_estimate.count}\` (\`${analysis.token_estimate.accuracy}\`, \`${analysis.token_estimate.provider}:${analysis.token_estimate.model}\`)`,
      `- **Contains Code:** ${analysis.classification.contains_code}`,
      `- **Contains Constraints:** ${analysis.classification.contains_constraints}`,
      "",
      "## Extracted Constraints",
      ...(analysis.constraints.constraints.length
        ? analysis.constraints.constraints.map((c) => `- ${c}`)
        : ["- None detected"]),
      "",
      `## Locked Protected Spans (${analysis.protected_spans.length})`,
      ...analysis.protected_spans
        .slice(0, 50)
        .map((s) => `- \`[${s.category}]\` \`${s.value}\``)
    ];

    await this.host.openReadOnlyDocument("Project T Analysis", reportLines.join("\n"), "markdown");
    return analysis;
  }

  async selectRelevantFiles(): Promise<ContextSelectResponseWire | null> {
    const root = this.host.getActiveWorkspaceRoot();
    if (!root) {
      this.host.showWarning("Open a workspace folder before running workspace relevance analysis.");
      return null;
    }

    if (!this.workspaceAllowlist.isApproved(root)) {
      const approved = await this.host.confirmWorkspaceApproval(root);
      if (!approved) {
        this.host.showInfo("Workspace relevance analysis cancelled (workspace not approved).");
        return null;
      }
      await this.workspaceAllowlist.approve(root);
    }

    const taskDescription = await this.host.askInputBox(
      "Describe the coding task to rank relevant workspace files",
      "e.g., Fix JWT middleware validation without changing schema"
    );
    if (!taskDescription?.trim()) {
      return null;
    }

    const settings = this.host.getSettings();
    const response = await this.client.selectContext({
      task_description: taskDescription.trim(),
      workspace_root: root,
      max_files: 15,
      max_tokens: 8000,
      provider: settings.defaultProvider,
      model: settings.defaultModel
    });

    const lines = [
      "# Project T Relevant Workspace Files",
      "",
      `- **Workspace:** \`${root}\``,
      `- **Total Estimated Tokens:** \`${response.total_tokens}\` (\`${response.accuracy}\`)`,
      "",
      "| File | Score | Est. Tokens | Pinned | Reason |",
      "|---|---:|---:|---:|---|",
      ...response.selected_files.map(
        (f) =>
          `| \`${f.relative_path}\` | ${f.score.toFixed(2)} | ${f.estimated_tokens} | ${f.pinned} | ${f.reason} |`
      )
    ];

    await this.host.openReadOnlyDocument("Project T Relevant Files", lines.join("\n"), "markdown");
    return response;
  }

  async compressTerminalOutput(): Promise<OptimizationResult | null> {
    const captured = await captureSelectedTerminalText(this.host.terminalHost);
    if (!captured.text) {
      this.host.showWarning(
        "Select text in the active terminal (or copy terminal output to clipboard) before compressing."
      );
      return null;
    }

    const settings = this.host.getSettings();
    const { result } = await this.client.compressLogs({
      output: captured.text,
      context_lines: 5,
      provider: settings.defaultProvider,
      model: settings.defaultModel
    });

    this.stateStore.recordRun(result, "compress_terminal");
    await this.host.onStateChanged?.();

    const vm = buildPreviewViewModel(result);
    const header =
      `# Compressed Terminal Output (${vm.tokensSaved} tokens saved, ${vm.reductionLabel}, ${vm.accuracyLabel})\n` +
      `# Original captured from: ${captured.source}\n\n`;

    await this.host.openReadOnlyDocument(
      "Project T Compressed Terminal Output",
      `${header}${result.optimizedContent}`,
      "log"
    );
    await this.host.terminalHost.clipboard.writeText(result.optimizedContent);
    this.host.showInfo(
      `Compressed terminal output (-${vm.tokensSaved} tokens, ${vm.accuracyLabel}) opened in preview and copied to clipboard.`
    );
    return result;
  }

  async configureToken(): Promise<boolean> {
    const token = await this.host.askInputBox(
      "Enter Project T Local Runtime bearer token (stored in VS Code SecretStorage)",
      "Paste installation bearer token",
      true
    );
    if (!token?.trim()) {
      return false;
    }
    await this.tokenStore.setToken(token);
    await this.host.onStateChanged?.();
    this.host.showInfo("Project T Local Runtime token saved securely in VS Code SecretStorage.");
    return true;
  }

  async checkRuntimeHealth(): Promise<boolean> {
    try {
      const h = await this.client.health();
      this.host.showInfo(
        `Project T Local Runtime is ${h.status} (v${h.version}, SQLite=${h.sqlite_ready ? "ready" : "unavailable"}).`
      );
      return h.status === "ok";
    } catch (error) {
      const msg = error instanceof Error ? error.message : String(error);
      this.host.showError(msg);
      return false;
    }
  }
}
