import { describe, expect, it } from "vitest";
import {
  CONTENT_TYPES,
  OPTIMIZATION_MODES,
  fromWireOptimizationResult,
  toWireOptimizationRequest,
  validateOptimizationRequestWire,
  validateOptimizationResultWire,
  validateTokenCountResultWire,
  type OptimizationRequest,
  type OptimizationResultWire
} from "../src/index.js";

describe("@project-t/contracts", () => {
  it("exposes canonical enums matching schema definitions", () => {
    expect(OPTIMIZATION_MODES).toEqual(["safe", "balanced", "aggressive"]);
    expect(CONTENT_TYPES).toEqual([
      "prompt",
      "developer_prompt",
      "source_code",
      "json",
      "documentation",
      "terminal_output",
      "conversation",
      "tool_result"
    ]);
  });

  it("maps camelCase SDK OptimizationRequest to snake_case wire format", () => {
    const sdkReq: OptimizationRequest = {
      content: "Fix auth middleware without changing schema.",
      contentType: "developer_prompt",
      provider: "openai",
      model: "example-model",
      mode: "balanced",
      preserveIdentifiers: true
    };

    const wire = toWireOptimizationRequest(sdkReq, {
      integration: "vscode",
      semanticCompression: false
    });

    expect(wire).toEqual({
      content: "Fix auth middleware without changing schema.",
      content_type: "developer_prompt",
      provider: "openai",
      model: "example-model",
      mode: "balanced",
      integration: "vscode",
      optimization: {
        deduplicate: true,
        semantic_compression: false,
        context_filtering: true,
        preserve_identifiers: true
      }
    });

    const check = validateOptimizationRequestWire(wire);
    expect(check.ok).toBe(true);
  });

  it("maps wire OptimizationResultWire to camelCase SDK OptimizationResult", () => {
    const wire: OptimizationResultWire = {
      request_id: "req_001",
      original_content: "Original prompt text",
      optimized_content: "Optimized text",
      tokens: {
        original: 120,
        optimized: 80,
        saved: 40,
        reduction_percentage: 33.33,
        accuracy: "estimated"
      },
      validation: {
        passed: true,
        constraints_preserved: true,
        identifiers_preserved: true,
        structure_preserved: true,
        quality_score: 0.96
      },
      optimization: {
        methods: ["whitespace_normalization", "rule_based_compression"],
        mode: "balanced"
      },
      duration_ms: 14,
      warnings: []
    };

    expect(validateOptimizationResultWire(wire).ok).toBe(true);

    const sdkRes = fromWireOptimizationResult(wire);
    expect(sdkRes).toEqual({
      requestId: "req_001",
      originalContent: "Original prompt text",
      optimizedContent: "Optimized text",
      originalTokens: 120,
      optimizedTokens: 80,
      tokensSaved: 40,
      reductionPercentage: 33.33,
      validationPassed: true,
      accuracy: "estimated",
      methods: ["whitespace_normalization", "rule_based_compression"],
      warnings: [],
      durationMs: 14
    });
  });

  it("rejects unknown fields and invalid enum values at runtime", () => {
    const badReq = validateOptimizationRequestWire({
      content: "Hello",
      mode: "turbo",
      unexpected_extra: 123
    });
    expect(badReq.ok).toBe(false);
    if (!badReq.ok) {
      expect(badReq.issues.map((i) => i.path)).toContain("mode");
      expect(badReq.issues.map((i) => i.path)).toContain("unexpected_extra");
    }

    const badCount = validateTokenCountResultWire({
      count: -1,
      accuracy: "provider_guessed",
      model: "",
      provider: "openai"
    });
    expect(badCount.ok).toBe(false);
  });
});
