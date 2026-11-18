import type { AccuracyLevel, OptimizationMode, OptimizationResult } from "@project-t/contracts";

export interface ModeOptionDescriptor {
  mode: OptimizationMode;
  label: string;
  description: string;
}

export const OPTIMIZATION_MODE_DESCRIPTORS: readonly ModeOptionDescriptor[] = [
  {
    mode: "safe",
    label: "Safe",
    description: "Low-risk deterministic normalization and strict preservation."
  },
  {
    mode: "balanced",
    label: "Balanced",
    description: "Deduplication, rule-based compression, and safe context filtering."
  },
  {
    mode: "aggressive",
    label: "Aggressive",
    description: "Broader compaction and pruning with hard constraint/identifier validation."
  }
] as const;

export interface OptimizationPreviewViewModel {
  requestId: string;
  originalTokens: number;
  optimizedTokens: number;
  tokensSaved: number;
  reductionLabel: string;
  accuracyLabel: string;
  accuracy: AccuracyLevel;
  fallbackTriggered: boolean;
  methods: string[];
  warnings: string[];
}

export function buildPreviewViewModel(result: OptimizationResult): OptimizationPreviewViewModel {
  return {
    requestId: result.requestId,
    originalTokens: result.originalTokens,
    optimizedTokens: result.optimizedTokens,
    tokensSaved: result.tokensSaved,
    reductionLabel: `${result.reductionPercentage.toFixed(2)}%`,
    accuracyLabel: result.accuracy === "exact" ? "Exact count" : "Estimated count",
    accuracy: result.accuracy,
    fallbackTriggered: !result.validationPassed || result.tokensSaved <= 0,
    methods: [...result.methods],
    warnings: [...result.warnings]
  };
}
