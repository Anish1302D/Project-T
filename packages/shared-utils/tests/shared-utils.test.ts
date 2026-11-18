import { describe, expect, it } from "vitest";
import {
  calculateSavingsPercentage,
  formatAccuracyBadge,
  redactSecrets
} from "../src/index.js";

describe("@project-t/shared-utils", () => {
  it("computes token savings percentage safely", () => {
    expect(calculateSavingsPercentage(1200, 820)).toBe(31.67);
    expect(calculateSavingsPercentage(0, 0)).toBe(0);
    expect(calculateSavingsPercentage(100, 100)).toBe(0);
  });

  it("formats accuracy badges honestly", () => {
    expect(formatAccuracyBadge("exact")).toBe("Exact");
    expect(formatAccuracyBadge("estimated")).toBe("Estimated");
  });

  it("redacts bearer tokens and API keys in diagnostic messages", () => {
    const cleaned = redactSecrets("Auth failed with Bearer abcdef123456 and sk-secretkey9999");
    expect(cleaned).not.toContain("abcdef123456");
    expect(cleaned).not.toContain("sk-secretkey9999");
    expect(cleaned).toContain("[REDACTED]");
    expect(cleaned).toContain("[REDACTED_KEY]");
  });
});
