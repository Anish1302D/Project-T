import { queryFirstEditable, readEditorText, writeEditorText } from "./domHelpers.js";
import type { SiteAdapter } from "./types.js";

const CLAUDE_SELECTORS = [
  'div.ProseMirror[contenteditable="true"]',
  'fieldset div[contenteditable="true"]',
  '[aria-label*="Write your prompt" i][contenteditable="true"]'
] as const;

export const claudeAdapter: SiteAdapter = {
  id: "claude",
  displayName: "Claude",
  defaultProvider: "anthropic",
  defaultModel: "claude-sonnet-4",

  matchesHostname(hostname: string): boolean {
    return hostname.toLowerCase() === "claude.ai";
  },

  findPromptInput(doc: Document): HTMLElement | null {
    return queryFirstEditable(doc, CLAUDE_SELECTORS);
  },

  readPromptText(element: HTMLElement): string {
    return readEditorText(element);
  },

  writePromptText(element: HTMLElement, text: string): boolean {
    return writeEditorText(element, text);
  }
};
