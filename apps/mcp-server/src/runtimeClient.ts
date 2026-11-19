import * as fs from "node:fs";
import * as os from "node:os";
import * as path from "node:path";
import {
  fromWireOptimizationResult,
  validateOptimizationResultWire,
  validateTokenCountResultWire,
  type AnalyzeRequestWire,
  type AnalyzeResponseWire,
  type ContextCompressRequestWire,
  type ContextSelectRequestWire,
  type ContextSelectResponseWire,
  type ErrorResponseWire,
  type HealthResponseWire,
  type LogCompressRequestWire,
  type MetricsSummaryResponseWire,
  type OptimizationRequestWire,
  type OptimizationResult,
  type OptimizationResultWire,
  type ProvidersResponseWire,
  type RuntimeSettingsWire,
  type TokenCountRequestWire,
  type TokenCountResult
} from "@project-t/contracts";
import { redactSecrets } from "@project-t/shared-utils";

export const DEFAULT_LOCAL_RUNTIME_URL = "http://127.0.0.1:4765/api/v1";

export class McpRuntimeError extends Error {
  readonly statusCode: number;
  readonly errorCode: string;

  constructor(message: string, statusCode = 0, errorCode = "runtime_error") {
    super(redactSecrets(message));
    this.name = "McpRuntimeError";
    this.statusCode = statusCode;
    this.errorCode = errorCode;
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

export function resolveRuntimeToken(explicitToken?: string): string | undefined {
  if (explicitToken?.trim()) {
    return explicitToken.trim();
  }
  const envToken = process.env.PROJECT_T_RUNTIME_TOKEN?.trim();
  if (envToken) {
    return envToken;
  }
  const dataDir = process.env.PROJECT_T_DATA_DIR
    ? path.resolve(process.env.PROJECT_T_DATA_DIR)
    : path.join(os.homedir(), ".project-t");
  const tokenFile = path.join(dataDir, "auth_token");
  if (fs.existsSync(tokenFile)) {
    const fileVal = fs.readFileSync(tokenFile, "utf-8").trim();
    return fileVal || undefined;
  }
  return undefined;
}

export interface McpRuntimeClientOptions {
  baseUrl?: string;
  token?: string;
  getToken?: () => Promise<string | undefined>;
  fetchImpl?: typeof fetch;
  timeoutMs?: number;
  allowNonLoopback?: boolean;
}

export class McpRuntimeClient {
  private readonly baseUrl: string;
  private readonly getToken: () => Promise<string | undefined>;
  private readonly fetchImpl: typeof fetch;
  private readonly timeoutMs: number;

  constructor(options: McpRuntimeClientOptions = {}) {
    const rawUrl = (
      options.baseUrl ??
      process.env.PROJECT_T_RUNTIME_URL ??
      DEFAULT_LOCAL_RUNTIME_URL
    ).replace(/\/+$/, "");

    if (!options.allowNonLoopback && !isLoopbackRuntimeUrl(rawUrl)) {
      throw new McpRuntimeError(
        `Refusing non-loopback Local Runtime URL '${rawUrl}'. Must target 127.0.0.1 or localhost.`,
        0,
        "non_loopback_url"
      );
    }

    this.baseUrl = rawUrl;
    this.getToken = options.getToken ?? (async () => resolveRuntimeToken(options.token));
    this.fetchImpl = options.fetchImpl ?? fetch;
    this.timeoutMs = options.timeoutMs ?? 15_000;
  }

  async health(): Promise<HealthResponseWire> {
    return this.request<HealthResponseWire>("GET", "/health", undefined, false);
  }

  async optimize(request: OptimizationRequestWire): Promise<{
    wire: OptimizationResultWire;
    result: OptimizationResult;
  }> {
    const wire = await this.request<unknown>("POST", "/optimize", request);
    const checked = validateOptimizationResultWire(wire);
    if (!checked.ok) {
      throw new McpRuntimeError(
        `Invalid optimization contract returned: ${checked.issues.map((i) => i.path).join(", ")}`,
        502,
        "invalid_contract"
      );
    }
    return { wire: checked.value, result: fromWireOptimizationResult(checked.value) };
  }

  async analyze(request: AnalyzeRequestWire): Promise<AnalyzeResponseWire> {
    return this.request<AnalyzeResponseWire>("POST", "/analyze", request);
  }

  async compressLogs(request: LogCompressRequestWire): Promise<{
    wire: OptimizationResultWire;
    result: OptimizationResult;
  }> {
    const wire = await this.request<unknown>("POST", "/logs/compress", request);
    const checked = validateOptimizationResultWire(wire);
    if (!checked.ok) {
      throw new McpRuntimeError(
        `Invalid log compression contract returned: ${checked.issues.map((i) => i.path).join(", ")}`,
        502,
        "invalid_contract"
      );
    }
    return { wire: checked.value, result: fromWireOptimizationResult(checked.value) };
  }

  async selectContext(request: ContextSelectRequestWire): Promise<ContextSelectResponseWire> {
    return this.request<ContextSelectResponseWire>("POST", "/context/select", request);
  }

  async compressContext(request: ContextCompressRequestWire): Promise<{
    wire: OptimizationResultWire;
    result: OptimizationResult;
  }> {
    const wire = await this.request<unknown>("POST", "/context/compress", request);
    const checked = validateOptimizationResultWire(wire);
    if (!checked.ok) {
      throw new McpRuntimeError(
        `Invalid context compression contract returned: ${checked.issues.map((i) => i.path).join(", ")}`,
        502,
        "invalid_contract"
      );
    }
    return { wire: checked.value, result: fromWireOptimizationResult(checked.value) };
  }

  async countTokens(request: TokenCountRequestWire): Promise<TokenCountResult> {
    const wire = await this.request<unknown>("POST", "/count", request);
    const checked = validateTokenCountResultWire(wire);
    if (!checked.ok) {
      throw new McpRuntimeError(
        `Invalid token count contract returned: ${checked.issues.map((i) => i.path).join(", ")}`,
        502,
        "invalid_contract"
      );
    }
    return checked.value;
  }

  async metrics(integration?: string, windowDays = 30): Promise<MetricsSummaryResponseWire> {
    const params = new URLSearchParams({ window_days: String(windowDays) });
    if (integration) {
      params.set("integration", integration);
    }
    return this.request<MetricsSummaryResponseWire>("GET", `/metrics?${params.toString()}`);
  }

  async getSettings(): Promise<RuntimeSettingsWire> {
    return this.request<RuntimeSettingsWire>("GET", "/settings");
  }

  async providers(): Promise<ProvidersResponseWire> {
    return this.request<ProvidersResponseWire>("GET", "/providers");
  }

  private async request<T>(
    method: "GET" | "POST",
    endpoint: string,
    body?: unknown,
    requireAuth = true
  ): Promise<T> {
    const headers: Record<string, string> = { Accept: "application/json" };
    if (requireAuth) {
      const token = await this.getToken();
      if (!token) {
        throw new McpRuntimeError(
          "Local Runtime bearer token missing. Set PROJECT_T_RUNTIME_TOKEN or initialize Local Runtime.",
          401,
          "missing_token"
        );
      }
      headers.Authorization = `Bearer ${token}`;
    }

    let serialized: string | undefined;
    if (body !== undefined) {
      headers["Content-Type"] = "application/json";
      serialized = JSON.stringify(body);
    }

    const controller = new AbortController();
    const timer = setTimeout(() => controller.abort(), this.timeoutMs);

    try {
      const response = await this.fetchImpl(`${this.baseUrl}${endpoint}`, {
        method,
        headers,
        body: serialized,
        signal: controller.signal
      });
      const text = await response.text();
      let parsed: unknown;
      if (text) {
        try {
          parsed = JSON.parse(text);
        } catch {
          parsed = undefined;
        }
      }

      if (!response.ok) {
        const errObj = parsed as Partial<ErrorResponseWire> | undefined;
        throw new McpRuntimeError(
          errObj?.error?.message ?? `Local Runtime returned HTTP ${response.status}`,
          response.status,
          errObj?.error?.code ?? `http_${response.status}`
        );
      }
      return parsed as T;
    } catch (error) {
      if (error instanceof McpRuntimeError) {
        throw error;
      }
      if (error instanceof Error && error.name === "AbortError") {
        throw new McpRuntimeError(
          `Local Runtime request timed out after ${this.timeoutMs} ms`,
          504,
          "timeout"
        );
      }
      const message = error instanceof Error ? error.message : "Unknown network error";
      throw new McpRuntimeError(
        `Failed to connect to Project T Local Runtime at ${this.baseUrl}: ${message}`,
        0,
        "connection_failed"
      );
    } finally {
      clearTimeout(timer);
    }
  }
}
