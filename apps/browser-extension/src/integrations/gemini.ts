import { queryFirstEditable, readEditorText, writeEditorText } from "./domHelpers.js";
import type { SiteAdapter } from "./types.js";

const GEMINI_SELECTORS = [
  'rich-textarea .ql-editor[contenteditable="true"]',
  '.ql-editor[contenteditable="true"]',
  'div[role="textbox"][aria-label*="prompt" i][contenteditable="true"]',
  'rich-textarea textarea'
] as const;

export const geminiAdapter: SiteAdapter = {
  id: "gemini",
  displayName: "Gemini",
  defaultProvider: "google",
  defaultModel: "gemini-2.5-pro",

  matchesHostname(hostname: string): boolean {
    return hostname.toLowerCase() === "gemini.google.com";
  },

  findPromptInput(doc: Document): HTMLElement | null {
    return queryFirstEditable(doc, GEMINI_SELECTORS);
  },

  readPromptText(element: HTMLElement): string {
    return readEditorText(element);
  },

  writePromptText(element: HTMLElement, text: string): boolean {
    return writeEditorText(element, text);
  }
};
