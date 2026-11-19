import {
  ACCURACY_LEVELS,
  CONTENT_TYPES,
  INTEGRATION_SOURCES,
  OPTIMIZATION_MODES,
  type AccuracyLevel,
  type ContentType,
  type IntegrationSource,
  type OptimizationMode,
  type OptimizationRequestWire,
  type OptimizationResultWire,
  type TokenCountResultWire
} from "./wire.js";

export interface ValidationIssue {
  path: string;
  message: string;
}

export type ValidationOutcome<T> =
  | { ok: true; value: T }
  | { ok: false; issues: ValidationIssue[] };

function isRecord(value: unknown): value is Record<string, unknown> {
  return typeof value === "object" && value !== null && !Array.isArray(value);
}

function checkAllowedKeys(
  obj: Record<string, unknown>,
  allowed: ReadonlySet<string>,
  prefix: string,
  issues: ValidationIssue[]
): void {
  for (const key of Object.keys(obj)) {
    if (!allowed.has(key)) {
      issues.push({ path: prefix ? `${prefix}.${key}` : key, message: "Unexpected property" });
    }
  }
}

export function isOptimizationMode(value: unknown): value is OptimizationMode {
  return typeof value === "string" && (OPTIMIZATION_MODES as readonly string[]).includes(value);
}

export function isContentType(value: unknown): value is ContentType {
  return typeof value === "string" && (CONTENT_TYPES as readonly string[]).includes(value);
}

export function isAccuracyLevel(value: unknown): value is AccuracyLevel {
  return typeof value === "string" && (ACCURACY_LEVELS as readonly string[]).includes(value);
}

export function isIntegrationSource(value: unknown): value is IntegrationSource {
  return (
    typeof value === "string" && (INTEGRATION_SOURCES as readonly string[]).includes(value)
  );
}

const REQUEST_KEYS = new Set([
  "content",
  "content_type",
  "provider",
  "model",
  "mode",
  "integration",
  "project_id",
  "optimization"
]);

const OPTIMIZATION_FLAG_KEYS = new Set([
  "deduplicate",
  "semantic_compression",
  "context_filtering",
  "preserve_identifiers"
]);

export function validateOptimizationRequestWire(
  input: unknown
): ValidationOutcome<OptimizationRequestWire> {
  const issues: ValidationIssue[] = [];
  if (!isRecord(input)) {
    return { ok: false, issues: [{ path: "", message: "Expected an object" }] };
  }

  checkAllowedKeys(input, REQUEST_KEYS, "", issues);

  if (typeof input.content !== "string" || input.content.length < 1) {
    issues.push({ path: "content", message: "Must be a non-empty string" });
  }
  if (input.content_type !== undefined && !isContentType(input.content_type)) {
    issues.push({ path: "content_type", message: "Invalid ContentType enum value" });
  }
  if (input.provider !== undefined && typeof input.provider !== "string") {
    issues.push({ path: "provider", message: "Must be a string" });
  }
  if (input.model !== undefined && typeof input.model !== "string") {
    issues.push({ path: "model", message: "Must be a string" });
  }
  if (input.mode !== undefined && !isOptimizationMode(input.mode)) {
    issues.push({ path: "mode", message: "Invalid OptimizationMode enum value" });
  }
  if (input.integration !== undefined && !isIntegrationSource(input.integration)) {
    issues.push({ path: "integration", message: "Invalid IntegrationSource enum value" });
  }
  if (input.project_id !== undefined && typeof input.project_id !== "string") {
    issues.push({ path: "project_id", message: "Must be a string" });
  }
  if (input.optimization !== undefined) {
    if (!isRecord(input.optimization)) {
      issues.push({ path: "optimization", message: "Must be an object" });
    } else {
      checkAllowedKeys(input.optimization, OPTIMIZATION_FLAG_KEYS, "optimization", issues);
      for (const flagKey of OPTIMIZATION_FLAG_KEYS) {
        const val = input.optimization[flagKey];
        if (val !== undefined && typeof val !== "boolean") {
          issues.push({ path: `optimization.${flagKey}`, message: "Must be a boolean" });
        }
      }
    }
  }

  if (issues.length > 0) {
    return { ok: false, issues };
  }
  return { ok: true, value: input as unknown as OptimizationRequestWire };
}

const RESULT_KEYS = new Set([
  "request_id",
  "original_content",
  "optimized_content",
  "tokens",
  "validation",
  "optimization",
  "duration_ms",
  "warnings"
]);

const TOKEN_SUMMARY_KEYS = new Set([
  "original",
  "optimized",
  "saved",
  "reduction_percentage",
  "accuracy"
]);

const VALIDATION_SUMMARY_KEYS = new Set([
  "passed",
  "constraints_preserved",
  "identifiers_preserved",
  "structure_preserved",
  "quality_score"
]);

const OPT_SUMMARY_KEYS = new Set(["methods", "mode"]);

export function validateOptimizationResultWire(
  input: unknown
): ValidationOutcome<OptimizationResultWire> {
  const issues: ValidationIssue[] = [];
  if (!isRecord(input)) {
    return { ok: false, issues: [{ path: "", message: "Expected an object" }] };
  }

  checkAllowedKeys(input, RESULT_KEYS, "", issues);

  if (typeof input.request_id !== "string" || input.request_id.length < 1) {
    issues.push({ path: "request_id", message: "Must be a non-empty string" });
  }
  if (typeof input.original_content !== "string") {
    issues.push({ path: "original_content", message: "Must be a string" });
  }
  if (typeof input.optimized_content !== "string") {
    issues.push({ path: "optimized_content", message: "Must be a string" });
  }
  if (
    typeof input.duration_ms !== "number" ||
    !Number.isInteger(input.duration_ms) ||
    input.duration_ms < 0
  ) {
    issues.push({ path: "duration_ms", message: "Must be a non-negative integer" });
  }
  if (
    !Array.isArray(input.warnings) ||
    input.warnings.some((w) => typeof w !== "string")
  ) {
    issues.push({ path: "warnings", message: "Must be an array of strings" });
  }

  if (!isRecord(input.tokens)) {
    issues.push({ path: "tokens", message: "Must be an object" });
  } else {
    checkAllowedKeys(input.tokens, TOKEN_SUMMARY_KEYS, "tokens", issues);
    if (
      typeof input.tokens.original !== "number" ||
      !Number.isInteger(input.tokens.original) ||
      input.tokens.original < 0
    ) {
      issues.push({ path: "tokens.original", message: "Must be a non-negative integer" });
    }
    if (
      typeof input.tokens.optimized !== "number" ||
      !Number.isInteger(input.tokens.optimized) ||
      input.tokens.optimized < 0
    ) {
      issues.push({ path: "tokens.optimized", message: "Must be a non-negative integer" });
    }
    if (typeof input.tokens.saved !== "number" || !Number.isInteger(input.tokens.saved)) {
      issues.push({ path: "tokens.saved", message: "Must be an integer" });
    }
    if (
      typeof input.tokens.reduction_percentage !== "number" ||
      !Number.isFinite(input.tokens.reduction_percentage)
    ) {
      issues.push({ path: "tokens.reduction_percentage", message: "Must be a finite number" });
    }
    if (!isAccuracyLevel(input.tokens.accuracy)) {
      issues.push({ path: "tokens.accuracy", message: "Must be 'exact' or 'estimated'" });
    }
  }

  if (!isRecord(input.validation)) {
    issues.push({ path: "validation", message: "Must be an object" });
  } else {
    checkAllowedKeys(input.validation, VALIDATION_SUMMARY_KEYS, "validation", issues);
    if (typeof input.validation.passed !== "boolean") {
      issues.push({ path: "validation.passed", message: "Must be a boolean" });
    }
    if (typeof input.validation.constraints_preserved !== "boolean") {
      issues.push({ path: "validation.constraints_preserved", message: "Must be a boolean" });
    }
    if (typeof input.validation.identifiers_preserved !== "boolean") {
      issues.push({ path: "validation.identifiers_preserved", message: "Must be a boolean" });
    }
    if (
      input.validation.structure_preserved !== undefined &&
      typeof input.validation.structure_preserved !== "boolean"
    ) {
      issues.push({ path: "validation.structure_preserved", message: "Must be a boolean" });
    }
    if (input.validation.quality_score !== undefined) {
      if (
        typeof input.validation.quality_score !== "number" ||
        input.validation.quality_score < 0 ||
        input.validation.quality_score > 1
      ) {
        issues.push({
          path: "validation.quality_score",
          message: "Must be a number in [0, 1]"
        });
      }
    }
  }

  if (!isRecord(input.optimization)) {
    issues.push({ path: "optimization", message: "Must be an object" });
  } else {
    checkAllowedKeys(input.optimization, OPT_SUMMARY_KEYS, "optimization", issues);
    if (
      !Array.isArray(input.optimization.methods) ||
      input.optimization.methods.some((m) => typeof m !== "string")
    ) {
      issues.push({ path: "optimization.methods", message: "Must be an array of strings" });
    }
    if (!isOptimizationMode(input.optimization.mode)) {
      issues.push({ path: "optimization.mode", message: "Invalid OptimizationMode enum value" });
    }
  }

  if (issues.length > 0) {
    return { ok: false, issues };
  }
  return { ok: true, value: input as unknown as OptimizationResultWire };
}

const TOKEN_COUNT_KEYS = new Set(["count", "accuracy", "model", "provider"]);

export function validateTokenCountResultWire(
  input: unknown
): ValidationOutcome<TokenCountResultWire> {
  const issues: ValidationIssue[] = [];
  if (!isRecord(input)) {
    return { ok: false, issues: [{ path: "", message: "Expected an object" }] };
  }

  checkAllowedKeys(input, TOKEN_COUNT_KEYS, "", issues);

  if (typeof input.count !== "number" || !Number.isInteger(input.count) || input.count < 0) {
    issues.push({ path: "count", message: "Must be a non-negative integer" });
  }
  if (!isAccuracyLevel(input.accuracy)) {
    issues.push({ path: "accuracy", message: "Must be 'exact' or 'estimated'" });
  }
  if (typeof input.model !== "string" || input.model.length < 1) {
    issues.push({ path: "model", message: "Must be a non-empty string" });
  }
  if (typeof input.provider !== "string" || input.provider.length < 1) {
    issues.push({ path: "provider", message: "Must be a non-empty string" });
  }

  if (issues.length > 0) {
    return { ok: false, issues };
  }
  return { ok: true, value: input as unknown as TokenCountResultWire };
}
