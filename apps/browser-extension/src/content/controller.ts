import type { OptimizationResult } from "@project-t/contracts";
import { buildPreviewViewModel } from "@project-t/shared-ui";
import type { SiteAdapter } from "../integrations/types.js";

export type PromptOptimizeFn = (params: {
  text: string;
  siteId: SiteAdapter["id"];
  provider: string;
  model: string;
}) => Promise<OptimizationResult>;

export interface BrowserControllerOptions {
  doc: Document;
  adapter: SiteAdapter;
  optimizePrompt: PromptOptimizeFn;
  copyToClipboard?: (text: string) => Promise<boolean>;
}

interface AppliedSnapshot {
  element: HTMLElement;
  originalText: string;
  optimizedText: string;
  requestId: string;
}

/**
 * Explicit user-triggered controller mounted on supported AI prompt pages.
 * Never intercepts background fetch/XHR traffic or reads unrelated page/cookie data.
 */
export class BrowserPromptController {
  private readonly doc: Document;
  private readonly adapter: SiteAdapter;
  private readonly optimizePrompt: PromptOptimizeFn;
  private readonly copyToClipboard: (text: string) => Promise<boolean>;

  private triggerBtn: HTMLButtonElement | null = null;
  private overlayEl: HTMLDivElement | null = null;
  private pendingResult: OptimizationResult | null = null;
  private pendingTarget: HTMLElement | null = null;
  private lastApplied: AppliedSnapshot | null = null;

  constructor(options: BrowserControllerOptions) {
    this.doc = options.doc;
    this.adapter = options.adapter;
    this.optimizePrompt = options.optimizePrompt;
    this.copyToClipboard =
      options.copyToClipboard ??
      (async (text: string) => {
        try {
          const nav = this.doc.defaultView?.navigator;
          if (nav?.clipboard?.writeText) {
            await nav.clipboard.writeText(text);
            return true;
          }
        } catch {
          return false;
        }
        return false;
      });
  }

  mount(): void {
    if (this.triggerBtn || !this.doc.body) {
      return;
    }
    const btn = this.doc.createElement("button");
    btn.type = "button";
    btn.className = "pt-trigger-btn";
    btn.setAttribute("data-project-t", "trigger");
    btn.textContent = "Optimize Prompt";
    btn.addEventListener("click", () => {
      void this.triggerOptimize();
    });
    this.doc.body.appendChild(btn);
    this.triggerBtn = btn;
  }

  unmount(): void {
    this.triggerBtn?.remove();
    this.triggerBtn = null;
    this.overlayEl?.remove();
    this.overlayEl = null;
  }

  getLastApplied(): AppliedSnapshot | null {
    return this.lastApplied;
  }

  async triggerOptimize(): Promise<OptimizationResult | null> {
    const target = this.adapter.findPromptInput(this.doc);
    if (!target) {
      this.renderStatusOverlay("Project T", "No active prompt input detected on this page.");
      return null;
    }

    const rawText = this.adapter.readPromptText(target);
    if (!rawText.trim()) {
      this.renderStatusOverlay("Project T", "Enter a prompt before optimizing.");
      return null;
    }

    this.pendingTarget = target;
    try {
      const result = await this.optimizePrompt({
        text: rawText,
        siteId: this.adapter.id,
        provider: this.adapter.defaultProvider,
        model: this.adapter.defaultModel
      });
      this.pendingResult = result;
      this.renderReviewOverlay(result);
      return result;
    } catch (err) {
      const message = err instanceof Error ? err.message : "Optimization failed";
      this.renderStatusOverlay("Project T Error", message);
      return null;
    }
  }

  async acceptPending(): Promise<boolean> {
    if (!this.pendingResult || !this.pendingTarget) {
      return false;
    }
    const result = this.pendingResult;
    const written = this.adapter.writePromptText(this.pendingTarget, result.optimizedContent);
    if (!written) {
      const copied = await this.copyToClipboard(result.optimizedContent);
      this.renderStatusOverlay(
        "Project T",
        copied
          ? "Editor blocked direct replacement. Optimized prompt copied to clipboard."
          : "Editor blocked direct replacement. Copy the optimized prompt manually."
      );
      return false;
    }

    this.lastApplied = {
      element: this.pendingTarget,
      originalText: result.originalContent,
      optimizedText: result.optimizedContent,
      requestId: result.requestId
    };
    this.pendingResult = null;
    this.renderAppliedOverlay(result);
    return true;
  }

  rejectPending(): void {
    this.pendingResult = null;
    this.pendingTarget = null;
    this.closeOverlay();
  }

  restoreOriginal(): boolean {
    if (!this.lastApplied) {
      return false;
    }
    const ok = this.adapter.writePromptText(
      this.lastApplied.element,
      this.lastApplied.originalText
    );
    if (ok) {
      this.lastApplied = null;
      this.closeOverlay();
    }
    return ok;
  }

  closeOverlay(): void {
    this.overlayEl?.remove();
    this.overlayEl = null;
  }

  private ensureOverlay(): HTMLDivElement {
    if (this.overlayEl) {
      this.overlayEl.replaceChildren();
      return this.overlayEl;
    }
    const box = this.doc.createElement("div");
    box.className = "pt-review-overlay";
    box.setAttribute("data-project-t", "overlay");
    this.doc.body.appendChild(box);
    this.overlayEl = box;
    return box;
  }

  private renderStatusOverlay(title: string, message: string): void {
    const box = this.ensureOverlay();
    const header = this.doc.createElement("div");
    header.className = "pt-review-header";
    const strong = this.doc.createElement("strong");
    strong.textContent = title;
    const closeBtn = this.doc.createElement("button");
    closeBtn.type = "button";
    closeBtn.className = "pt-btn";
    closeBtn.textContent = "Close";
    closeBtn.addEventListener("click", () => this.closeOverlay());
    header.append(strong, closeBtn);

    const p = this.doc.createElement("p");
    p.textContent = message;
    box.append(header, p);
  }

  private renderReviewOverlay(result: OptimizationResult): void {
    const vm = buildPreviewViewModel(result);
    const box = this.ensureOverlay();

    const header = this.doc.createElement("div");
    header.className = "pt-review-header";
    const title = this.doc.createElement("strong");
    title.textContent = `${this.adapter.displayName} Preview (-${vm.tokensSaved} tokens, ${vm.reductionLabel})`;
    const badge = this.doc.createElement("span");
    badge.className = "pt-badge";
    badge.setAttribute("data-project-t", "accuracy-badge");
    badge.textContent = vm.accuracyLabel;
    header.append(title, badge);

    const origLabel = this.doc.createElement("div");
    origLabel.textContent = `Original (${vm.originalTokens} tokens):`;
    const origBox = this.doc.createElement("div");
    origBox.className = "pt-diff-box";
    origBox.setAttribute("data-project-t", "original-preview");
    origBox.textContent = result.originalContent;

    const optLabel = this.doc.createElement("div");
    optLabel.textContent = `Optimized (${vm.optimizedTokens} tokens):`;
    const optBox = this.doc.createElement("div");
    optBox.className = "pt-diff-box";
    optBox.setAttribute("data-project-t", "optimized-preview");
    optBox.textContent = result.optimizedContent;

    const actions = this.doc.createElement("div");
    actions.className = "pt-actions";

    let fallbackNote: HTMLDivElement | null = null;
    if (!vm.fallbackTriggered) {
      const acceptBtn = this.doc.createElement("button");
      acceptBtn.type = "button";
      acceptBtn.className = "pt-btn pt-btn-primary";
      acceptBtn.setAttribute("data-project-t", "accept-btn");
      acceptBtn.textContent = "Accept";
      acceptBtn.addEventListener("click", () => {
        void this.acceptPending();
      });
      actions.appendChild(acceptBtn);
    } else {
      fallbackNote = this.doc.createElement("div");
      fallbackNote.textContent = `Kept original (${result.warnings[0] ?? "no meaningful savings"}).`;
    }

    const rejectBtn = this.doc.createElement("button");
    rejectBtn.type = "button";
    rejectBtn.className = "pt-btn";
    rejectBtn.setAttribute("data-project-t", "reject-btn");
    rejectBtn.textContent = "Reject";
    rejectBtn.addEventListener("click", () => this.rejectPending());
    actions.appendChild(rejectBtn);

    if (fallbackNote) {
      box.append(header, origLabel, origBox, optLabel, optBox, fallbackNote, actions);
    } else {
      box.append(header, origLabel, origBox, optLabel, optBox, actions);
    }
  }

  private renderAppliedOverlay(result: OptimizationResult): void {
    const vm = buildPreviewViewModel(result);
    const box = this.ensureOverlay();

    const header = this.doc.createElement("div");
    header.className = "pt-review-header";
    const title = this.doc.createElement("strong");
    title.textContent = `Applied (-${vm.tokensSaved} tokens, ${vm.reductionLabel})`;
    const badge = this.doc.createElement("span");
    badge.className = "pt-badge";
    badge.textContent = vm.accuracyLabel;
    header.append(title, badge);

    const actions = this.doc.createElement("div");
    actions.className = "pt-actions";

    const restoreBtn = this.doc.createElement("button");
    restoreBtn.type = "button";
    restoreBtn.className = "pt-btn";
    restoreBtn.setAttribute("data-project-t", "restore-btn");
    restoreBtn.textContent = "Restore Original";
    restoreBtn.addEventListener("click", () => {
      this.restoreOriginal();
    });

    const closeBtn = this.doc.createElement("button");
    closeBtn.type = "button";
    closeBtn.className = "pt-btn";
    closeBtn.textContent = "Done";
    closeBtn.addEventListener("click", () => this.closeOverlay());

    actions.append(restoreBtn, closeBtn);
    box.append(header, actions);
  }
}
