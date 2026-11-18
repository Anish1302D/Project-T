import type { AccuracyLevel } from "@project-t/contracts";

/**
 * Compute token savings percentage per Master Architecture Section 7.8:
 * ((Original tokens - Optimized tokens) / Original tokens) * 100
 */
export function calculateSavingsPercentage(
  originalTokens: number,
  optimizedTokens: number
): number {
  if (originalTokens <= 0) {
    return 0;
  }
  const raw = ((originalTokens - optimizedTokens) / originalTokens) * 100;
  return Number(raw.toFixed(2));
}

export function formatAccuracyBadge(accuracy: AccuracyLevel): string {
  return accuracy === "exact" ? "Exact" : "Estimated";
}

/**
 * Redact common bearer/API key patterns before rendering client diagnostic logs.
 */
export function redactSecrets(message: string): string {
  return message
    .replace(/Bearer\s+[A-Za-z0-9._\-+/=]+/gi, "Bearer [REDACTED]")
    .replace(/\b(sk-[A-Za-z0-9_-]{8,}|AIza[A-Za-z0-9_-]{12,})\b/g, "[REDACTED_KEY]");
}
