import { chatGptAdapter } from "./chatgpt.js";
import { claudeAdapter } from "./claude.js";
import { geminiAdapter } from "./gemini.js";
import type { SiteAdapter, SupportedSiteId } from "./types.js";

export const SITE_ADAPTERS: readonly SiteAdapter[] = [
  chatGptAdapter,
  claudeAdapter,
  geminiAdapter
] as const;

export function resolveSiteAdapterByHostname(hostname: string): SiteAdapter | null {
  return SITE_ADAPTERS.find((adapter) => adapter.matchesHostname(hostname)) ?? null;
}

export function resolveSiteAdapterById(id: SupportedSiteId | string): SiteAdapter | null {
  return SITE_ADAPTERS.find((adapter) => adapter.id === id) ?? null;
}

export type { SiteAdapter, SupportedSiteId } from "./types.js";
