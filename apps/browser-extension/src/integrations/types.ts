export type SupportedSiteId = "chatgpt" | "claude" | "gemini";

export interface SiteAdapter {
  readonly id: SupportedSiteId;
  readonly displayName: string;
  readonly defaultProvider: string;
  readonly defaultModel: string;

  matchesHostname(hostname: string): boolean;
  findPromptInput(doc: Document): HTMLElement | null;
  readPromptText(element: HTMLElement): string;
  writePromptText(element: HTMLElement, text: string): boolean;
}
