import type { OptimizationRequest, OptimizationResult, TokenCountResult } from "./sdk.js";
import type {
  IntegrationSource,
  OptimizationRequestWire,
  OptimizationResultWire,
  TokenCountResultWire
} from "./wire.js";

export interface ToWireRequestOptions {
  integration?: IntegrationSource;
  projectId?: string;
  deduplicate?: boolean;
  semanticCompression?: boolean;
  contextFiltering?: boolean;
}

/**
 * Convert an ergonomic TypeScript SDK request into the canonical snake_case HTTP wire DTO.
 */
export function toWireOptimizationRequest(
  request: OptimizationRequest,
  options: ToWireRequestOptions = {}
): OptimizationRequestWire {
  const wire: OptimizationRequestWire = {
    content: request.content,
    content_type: request.contentType,
    mode: request.mode,
    optimization: {
      deduplicate: options.deduplicate ?? true,
      semantic_compression: options.semanticCompression ?? false,
      context_filtering: options.contextFiltering ?? true,
      preserve_identifiers: request.preserveIdentifiers
    }
  };

  if (request.provider !== undefined) {
    wire.provider = request.provider;
  }
  if (request.model !== undefined) {
    wire.model = request.model;
  }
  if (options.integration !== undefined) {
    wire.integration = options.integration;
  }
  if (options.projectId !== undefined) {
    wire.project_id = options.projectId;
  }

  return wire;
}

/**
 * Convert a canonical snake_case HTTP wire result into the flat camelCase TypeScript SDK contract.
 */
export function fromWireOptimizationResult(wire: OptimizationResultWire): OptimizationResult {
  return {
    requestId: wire.request_id,
    originalContent: wire.original_content,
    optimizedContent: wire.optimized_content,
    originalTokens: wire.tokens.original,
    optimizedTokens: wire.tokens.optimized,
    tokensSaved: wire.tokens.saved,
    reductionPercentage: wire.tokens.reduction_percentage,
    validationPassed: wire.validation.passed,
    accuracy: wire.tokens.accuracy,
    methods: [...wire.optimization.methods],
    warnings: [...wire.warnings],
    durationMs: wire.duration_ms
  };
}

export function fromWireTokenCountResult(wire: TokenCountResultWire): TokenCountResult {
  return {
    count: wire.count,
    accuracy: wire.accuracy,
    model: wire.model,
    provider: wire.provider
  };
}
