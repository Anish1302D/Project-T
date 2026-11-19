import type { OptimizationResult } from "@project-t/contracts";
import { buildPreviewViewModel, type OptimizationPreviewViewModel } from "@project-t/shared-ui";

export interface SessionEditSnapshot {
  requestId: string;
  documentUri: string;
  startOffset: number;
  endOffset: number;
  originalText: string;
  optimizedText: string;
  appliedAtIso: string;
}

export interface MetadataHistoryEntry extends OptimizationPreviewViewModel {
  timestampIso: string;
  integrationAction: "optimize_selection" | "compress_terminal";
}

/**
 * Tracks metadata-only optimization history and an in-memory session undo buffer
 * so users can always restore the unmodified original text without persisting raw prompts.
 */
export class ReversibleOptimizationStore {
  private readonly history: MetadataHistoryEntry[] = [];
  private lastAppliedEdit: SessionEditSnapshot | null = null;
  private readonly maxHistory: number;

  constructor(maxHistory = 50) {
    this.maxHistory = maxHistory;
  }

  recordRun(
    result: OptimizationResult,
    action: MetadataHistoryEntry["integrationAction"],
    now: Date = new Date()
  ): MetadataHistoryEntry {
    const entry: MetadataHistoryEntry = {
      ...buildPreviewViewModel(result),
      timestampIso: now.toISOString(),
      integrationAction: action
    };
    this.history.unshift(entry);
    if (this.history.length > this.maxHistory) {
      this.history.length = this.maxHistory;
    }
    return entry;
  }

  setLastAppliedEdit(snapshot: SessionEditSnapshot): void {
    this.lastAppliedEdit = snapshot;
  }

  getLastAppliedEdit(): SessionEditSnapshot | null {
    return this.lastAppliedEdit;
  }

  clearLastAppliedEdit(): void {
    this.lastAppliedEdit = null;
  }

  getHistory(): readonly MetadataHistoryEntry[] {
    return this.history;
  }

  clearHistory(): void {
    this.history.length = 0;
  }
}
