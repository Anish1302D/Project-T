import {
  fromWireOptimizationResult,
  validateOptimizationResultWire,
  type ErrorResponseWire,
  type HealthResponseWire,
  type OptimizationRequestWire,
  type OptimizationResult
} from "@project-t/contracts";
import { redactSecrets } from "@project-t/shared-utils";
import type { ExtensionSettings } from "../shared/messages.js";

export class BridgeError extends Error {
  readonly code: string;

  constructor(message: string, code = "bridge_error") {
    super(redactSecrets(message));
    this.name = "BridgeError";
    this.code = code;
  }
}

export function isLoopbackRuntimeUrl(rawUrl: string): boolean {
  try {
    const parsed = new URL(rawUrl);
    if (parsed.protocol !== "http:" && parsed.protocol !== "https:") {
      return false;
    }
    const host = parsed.hostname.toLowerCase();
    return host === "127.0.0.1" || host === "localhost" || host === "::1" || host === "[::1]";
  } catch {
    return false;
  }
}

export async function checkRuntimeHealth(
  settings: ExtensionSettings,
  fetchImpl: typeof fetch = fetch
): Promise<HealthResponseWire> {
  const baseUrl = settings.runtimeUrl.replace(/\/+$/, "");
  if (!isLoopbackRuntimeUrl(baseUrl)) {
    throw new BridgeError(
      "Local Runtime URL must use loopback 127.0.0.1 or localhost.",
      "non_loopback_url"
    );
  }
  const res = await fetchImpl(`${baseUrl}/health`, {
    method: "GET",
    headers: { Accept: "application/json" }
  });
  if (!res.ok) {
    throw new BridgeError(`Local Runtime health check failed (HTTP ${res.status}).`, "health_failed");
  }
  return (await res.json()) as HealthResponseWire;
}

export async function optimizePromptViaRuntime(
  settings: ExtensionSettings,
  params: {
    text: string;
    provider?: string;
    model?: string;
  },
  fetchImpl: typeof fetch = fetch
): Promise<OptimizationResult> {
  const baseUrl = settings.runtimeUrl.replace(/\/+$/, "");
  if (!isLoopbackRuntimeUrl(baseUrl)) {
    throw new BridgeError(
      "Local Runtime URL must use loopback 127.0.0.1 or localhost.",
      "non_loopback_url"
    );
  }
  if (!settings.bearerToken.trim()) {
    throw new BridgeError(
      "Local Runtime installation bearer token is not configured. Open Extension Options to pair.",
      "missing_token"
    );
  }

  const wireReq: OptimizationRequestWire = {
    content: params.text,
    provider: params.provider ?? "local",
    model: params.model ?? "generic",
    mode: settings.mode,
    integration: "browser",
    optimization: {
      deduplicate: true,
      semantic_compression: false,
      context_filtering: true,
      preserve_identifiers: settings.preserveIdentifiers
    }
  };

  const res = await fetchImpl(`${baseUrl}/optimize`, {
    method: "POST",
    headers: {
      Accept: "application/json",
      "Content-Type": "application/json",
      Authorization: `Bearer ${settings.bearerToken.trim()}`
    },
    body: JSON.stringify(wireReq)
  });

  const text = await res.text();
  let parsed: unknown;
  if (text) {
    try {
      parsed = JSON.parse(text);
    } catch {
      parsed = undefined;
    }
  }

  if (!res.ok) {
    const errObj = parsed as Partial<ErrorResponseWire> | undefined;
    throw new BridgeError(
      errObj?.error?.message ?? `Local Runtime returned HTTP ${res.status}`,
      errObj?.error?.code ?? `http_${res.status}`
    );
  }

  const validated = validateOptimizationResultWire(parsed);
  if (!validated.ok) {
    throw new BridgeError(
      `Invalid Local Runtime response contract: ${validated.issues.map((i) => i.path).join(", ")}`,
      "invalid_contract"
    );
  }
  return fromWireOptimizationResult(validated.value);
}
