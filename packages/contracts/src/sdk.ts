import type { AccuracyLevel, ContentType, OptimizationMode } from "./wire.js";

/**
 * Ergonomic camelCase TypeScript SDK contracts matching
 * docs/token-optimization-platform-architecture.md Sections 8.1 and 12.
 */

export interface OptimizationRequest {
  content: string;
  contentType: ContentType;
  provider?: string;
  model?: string;
  mode: OptimizationMode;
  preserveIdentifiers: boolean;
}

export interface OptimizationResult {
  requestId: string;
  originalContent: string;
  optimizedContent: string;
  originalTokens: number;
  optimizedTokens: number;
  tokensSaved: number;
  reductionPercentage: number;
  validationPassed: boolean;
  accuracy: AccuracyLevel;
  methods: string[];
  warnings: string[];
  durationMs: number;
}

export interface TokenCountResult {
  count: number;
  accuracy: AccuracyLevel;
  model: string;
  provider: string;
}

export interface ModelRequest {
  provider: string;
  model: string;
  messages: Array<Record<string, unknown>>;
  system?: string;
  tools?: Array<Record<string, unknown>>;
}

export interface TokenizerAdapter {
  provider: string;
  countText(text: string, model: string): Promise<TokenCountResult>;
  countRequest?(request: ModelRequest): Promise<TokenCountResult>;
}
