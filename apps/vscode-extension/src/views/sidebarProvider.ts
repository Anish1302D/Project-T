import type {
  HealthResponseWire,
  MetricsSummaryResponseWire
} from "@project-t/contracts";
import * as vscode from "vscode";
import type { MetadataHistoryEntry } from "../commands/state.js";

export interface SidebarSnapshot {
  health: HealthResponseWire | null;
  healthError?: string;
  metrics: MetricsSummaryResponseWire | null;
  history: readonly MetadataHistoryEntry[];
}

export class SidebarTreeItem extends vscode.TreeItem {
  constructor(
    label: string,
    collapsibleState: vscode.TreeItemCollapsibleState,
    readonly children: SidebarTreeItem[] = [],
    description?: string,
    tooltip?: string,
    command?: vscode.Command
  ) {
    super(label, collapsibleState);
    this.description = description;
    this.tooltip = tooltip;
    this.command = command;
  }
}

export function buildSidebarTreeItems(snapshot: SidebarSnapshot): SidebarTreeItem[] {
  const statusLabel = snapshot.health
    ? snapshot.health.status === "ok"
      ? `Connected (v${snapshot.health.version})`
      : `Degraded (v${snapshot.health.version})`
    : "Disconnected";

  const statusChildren: SidebarTreeItem[] = [
    new SidebarTreeItem(
      "Runtime Status",
      vscode.TreeItemCollapsibleState.None,
      [],
      statusLabel,
      snapshot.healthError ?? "Local Runtime on 127.0.0.1:4765"
    ),
    new SidebarTreeItem(
      "SQLite Store",
      vscode.TreeItemCollapsibleState.None,
      [],
      snapshot.health?.sqlite_ready ? "Ready (metadata-only)" : "Unavailable"
    ),
    new SidebarTreeItem(
      "Configure Bearer Token",
      vscode.TreeItemCollapsibleState.None,
      [],
      "SecretStorage",
      "Store per-installation token securely in VS Code SecretStorage",
      {
        command: "projectT.configureToken",
        title: "Configure Token"
      }
    )
  ];

  const metricsChildren: SidebarTreeItem[] = snapshot.metrics
    ? [
        new SidebarTreeItem(
          "Total Runs",
          vscode.TreeItemCollapsibleState.None,
          [],
          String(snapshot.metrics.total_runs)
        ),
        new SidebarTreeItem(
          "Tokens Saved (30d)",
          vscode.TreeItemCollapsibleState.None,
          [],
          String(snapshot.metrics.total_tokens_saved),
          `Original: ${snapshot.metrics.total_original_tokens}, Optimized: ${snapshot.metrics.total_optimized_tokens}`
        ),
        new SidebarTreeItem(
          "Median Reduction",
          vscode.TreeItemCollapsibleState.None,
          [],
          `${(snapshot.metrics.median_reduction_percentage ?? 0).toFixed(2)}%`
        ),
        new SidebarTreeItem(
          "Fallbacks",
          vscode.TreeItemCollapsibleState.None,
          [],
          String(snapshot.metrics.fallback_count)
        )
      ]
    : [
        new SidebarTreeItem(
          "Metrics unavailable",
          vscode.TreeItemCollapsibleState.None,
          [],
          "Check token / runtime"
        )
      ];

  const historyChildren: SidebarTreeItem[] =
    snapshot.history.length > 0
      ? snapshot.history.slice(0, 15).map(
          (entry) =>
            new SidebarTreeItem(
              `${entry.integrationAction} (${entry.reductionLabel})`,
              vscode.TreeItemCollapsibleState.None,
              [],
              `${entry.tokensSaved} saved • ${entry.accuracyLabel}`,
              `Request ${entry.requestId} at ${entry.timestampIso}`
            )
        )
      : [
          new SidebarTreeItem(
            "No runs in this session",
            vscode.TreeItemCollapsibleState.None,
            [],
            "Metadata only"
          )
        ];

  return [
    new SidebarTreeItem("Local Runtime", vscode.TreeItemCollapsibleState.Expanded, statusChildren),
    new SidebarTreeItem("Metrics (Metadata-Only)", vscode.TreeItemCollapsibleState.Expanded, metricsChildren),
    new SidebarTreeItem("Session History", vscode.TreeItemCollapsibleState.Expanded, historyChildren)
  ];
}

export class ProjectTSidebarProvider implements vscode.TreeDataProvider<SidebarTreeItem> {
  private readonly emitter = new vscode.EventEmitter<SidebarTreeItem | undefined>();
  readonly onDidChangeTreeData = this.emitter.event;

  private snapshot: SidebarSnapshot = {
    health: null,
    metrics: null,
    history: []
  };

  updateSnapshot(next: SidebarSnapshot): void {
    this.snapshot = next;
    this.emitter.fire(undefined);
  }

  getTreeItem(element: SidebarTreeItem): vscode.TreeItem {
    return element;
  }

  getChildren(element?: SidebarTreeItem): SidebarTreeItem[] {
    if (!element) {
      return buildSidebarTreeItems(this.snapshot);
    }
    return element.children;
  }
}
