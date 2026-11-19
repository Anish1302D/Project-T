export interface ClipboardAdapter {
  readText(): Thenable<string> | Promise<string>;
  writeText(value: string): Thenable<void> | Promise<void>;
}

export interface TerminalSelectionHost {
  hasActiveTerminal: boolean;
  copySelection(): Thenable<unknown> | Promise<unknown>;
  clipboard: ClipboardAdapter;
}

/**
 * Captures user-selected terminal output via VS Code's terminal selection copy command
 * while preserving the user's prior clipboard contents. Falls back to explicit clipboard
 * text only if the terminal selection copy yields empty or no active terminal is selected.
 */
export async function captureSelectedTerminalText(
  host: TerminalSelectionHost
): Promise<{ text: string; source: "terminal_selection" | "clipboard" | "none" }> {
  const previousClipboard = await host.clipboard.readText();

  if (host.hasActiveTerminal) {
    try {
      await host.clipboard.writeText("");
      await host.copySelection();
      const copied = (await host.clipboard.readText()).trim();
      if (copied) {
        await host.clipboard.writeText(previousClipboard);
        return { text: copied, source: "terminal_selection" };
      }
    } finally {
      const current = await host.clipboard.readText();
      if (!current && previousClipboard) {
        await host.clipboard.writeText(previousClipboard);
      }
    }
  }

  const existing = previousClipboard.trim();
  if (existing) {
    return { text: existing, source: "clipboard" };
  }
  return { text: "", source: "none" };
}
