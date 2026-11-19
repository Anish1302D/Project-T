import { queryFirstEditable, readEditorText, writeEditorText } from "./domHelpers.js";
import type { SiteAdapter } from "./types.js";

const CHATGPT_SELECTORS = [
  "#prompt-textarea",
  'div[id="prompt-textarea"][contenteditable="true"]',
  'textarea[data-id="root"]',
  'form textarea:not([type="hidden"])'
] as const;

export const chatGptAdapter: SiteAdapter = {
  id: "chatgpt",
  displayName: "ChatGPT",
  defaultProvider: "openai",
  defaultModel: "gpt-4o",

  matchesHostname(hostname: string): boolean {
    const host = hostname.toLowerCase();
    return host === "chatgpt.com" || host === "chat.openai.com";
  },

  findPromptInput(doc: Document): HTMLElement | null {
    return queryFirstEditable(doc, CHATGPT_SELECTORS);
  },

  readPromptText(element: HTMLElement): string {
    return readEditorText(element);
  },

  writePromptText(element: HTMLElement, text: string): boolean {
    return writeEditorText(element, text);
  }
};
