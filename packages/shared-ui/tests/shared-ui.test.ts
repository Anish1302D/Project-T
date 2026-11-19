import { describe, expect, it } from "vitest";
import {
  OPTIMIZATION_MODE_DESCRIPTORS,
  buildPreviewViewModel,
  formatTokenCount,
  formatUsdCost
} from "../src/index.js";

describe("@project-t/shared-ui", () => {
  it("exposes all three optimization modes", () => {
    expect(OPTIMIZATION_MODE_DESCRIPTORS.map((m) => m.mode)).toEqual([
      "safe",
      "balanced",
      "aggressive"
    ]);
  });

  it("marks fallback state accurately in preview view models", () => {
    const vm = buildPreviewViewModel({
      requestId: "req_1",
      originalContent: "hello",
      optimizedContent: "hello",
      originalTokens: 10,
      optimizedTokens: 10,
      tokensSaved: 0,
      reductionPercentage: 0,
      validationPassed: true,
      accuracy: "estimated",
      methods: [],
      warnings: ["fallback_no_meaningful_savings"],
      durationMs: 2
    });
    expect(vm.fallbackTriggered).toBe(true);
    expect(vm.accuracyLabel).toBe("Estimated count");
  });

  it("formats token numbers and USD cost figures conservatively", () => {
    expect(formatTokenCount(12450)).toBe("12,450");
    expect(formatUsdCost(0.0042)).toBe("$0.0042");
    expect(formatUsdCost(1.5)).toBe("$1.50");
  });
});
