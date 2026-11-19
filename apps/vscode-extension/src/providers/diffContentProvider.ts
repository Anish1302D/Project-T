import * as vscode from "vscode";

export const DIFF_SCHEME = "project-t-diff";

/**
 * Provides read-only virtual documents (`project-t-diff:/...`) for side-by-side
 * before/after optimization diff previews without touching workspace files.
 */
export class DiffContentProvider implements vscode.TextDocumentContentProvider {
  private readonly contents = new Map<string, string>();
  private readonly changeEmitter = new vscode.EventEmitter<vscode.Uri>();

  readonly onDidChange = this.changeEmitter.event;

  setContent(uri: vscode.Uri, text: string): void {
    this.contents.set(uri.toString(), text);
    this.changeEmitter.fire(uri);
  }

  deleteContent(uri: vscode.Uri): void {
    this.contents.delete(uri.toString());
  }

  provideTextDocumentContent(uri: vscode.Uri): string {
    return this.contents.get(uri.toString()) ?? "";
  }

  static makePairUris(requestId: string, label = "preview"): {
    originalUri: vscode.Uri;
    optimizedUri: vscode.Uri;
  } {
    const safeId = encodeURIComponent(requestId);
    return {
      originalUri: vscode.Uri.parse(`${DIFF_SCHEME}:/${safeId}/${label}-original.txt`),
      optimizedUri: vscode.Uri.parse(`${DIFF_SCHEME}:/${safeId}/${label}-optimized.txt`)
    };
  }
}
