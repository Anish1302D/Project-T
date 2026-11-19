import {
  fromWireOptimizationResult,
  validateOptimizationResultWire,
  validateTokenCountResultWire,
  type AnalyzeRequestWire,
  type AnalyzeResponseWire,
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

export class RuntimeClientError extends Error {
  readonly statusCode: number;
  readonly errorCode: string;

  constructor(message: string, statusCode = 0, errorCode = "runtime_error") {
    super(redactSecrets(message));
    this.name = "RuntimeClientError";
    this.statusCode = statusCode;
    this.errorCode = errorCode;
  }
}

export function isLoopbackUrl(rawUrl: string): boolean {
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

export interface LocalRuntimeClientOptions {
  baseUrl?: string;
  getToken: () => Promise<string | undefined>;
  fetchImpl?: typeof fetch;
  timeoutMs?: number;
  allowNonLoopback?: boolean;
}

export class LocalRuntimeClient {
  private readonly baseUrl: string;
  private readonly getToken: () => Promise<string | undefined>;
  private readonly fetchImpl: typeof fetch;
  private readonly timeoutMs: number;

  constructor(options: LocalRuntimeClientOptions) {
    const rawUrl = (options.baseUrl ?? DEFAULT_LOCAL_RUNTIME_URL).replace(/\/+$/, "");
    if (!options.allowNonLoopback && !isLoopbackUrl(rawUrl)) {
      throw new RuntimeClientError(
        `Refusing non-loopback runtime URL '${rawUrl}'. Local Runtime must run on 127.0.0.1 / localhost.`,
        0,
        "non_loopback_url"
      );
    }
    this.baseUrl = rawUrl;
    this.getToken = options.getToken;
    this.fetchImpl = options.fetchImpl ?? fetch;
    this.timeoutMs = options.timeoutMs ?? 15_000;
  }

  async health(): Promise<HealthResponseWire> {
    return this.request<HealthResponseWire>("GET", "/health", undefined, { requireAuth: false });
  }

  async optimize(request: OptimizationRequestWire): Promise<{
    wire: OptimizationResultWire;
    result: OptimizationResult;
  }> {
    const wire = await this.request<unknown>("POST", "/optimize", request);
    const checked = validateOptimizationResultWire(wire);
    if (!checked.ok) {
      throw new RuntimeClientError(
        `Invalid optimization response contract: ${checked.issues.map((i) => i.path).join(", ")}`,
        502,
        "invalid_contract"
      );
    }
    return {
      wire: checked.value,
      result: fromWireOptimizationResult(checked.value)
    };
  }

  async count(request: TokenCountRequestWire): Promise<TokenCountResult> {
    const wire = await this.request<unknown>("POST", "/count", request);
    const checked = validateTokenCountResultWire(wire);
    if (!checked.ok) {
      throw new RuntimeClientError(
        `Invalid token count response contract: ${checked.issues.map((i) => i.path).join(", ")}`,
        502,
        "invalid_contract"
      );
    }
    return checked.value;
  }

  async analyze(request: AnalyzeRequestWire): Promise<AnalyzeResponseWire> {
    return this.request<AnalyzeResponseWire>("POST", "/analyze", request);
  }

  async selectContext(request: ContextSelectRequestWire): Promise<ContextSelectResponseWire> {
    return this.request<ContextSelectResponseWire>("POST", "/context/select", request);
  }

  async compressLogs(request: LogCompressRequestWire): Promise<{
    wire: OptimizationResultWire;
    result: OptimizationResult;
  }> {
    const wire = await this.request<unknown>("POST", "/logs/compress", request);
    const checked = validateOptimizationResultWire(wire);
    if (!checked.ok) {
      throw new RuntimeClientError(
        `Invalid log compression response contract: ${checked.issues.map((i) => i.path).join(", ")}`,
        502,
        "invalid_contract"
      );
    }
    return {
      wire: checked.value,
      result: fromWireOptimizationResult(checked.value)
    };
  }

  async metrics(windowDays = 30): Promise<MetricsSummaryResponseWire> {
    return this.request<MetricsSummaryResponseWire>(
      "GET",
      `/metrics?window_days=${encodeURIComponent(String(windowDays))}`
    );
  }

  async getSettings(): Promise<RuntimeSettingsWire> {
    return this.request<RuntimeSettingsWire>("GET", "/settings");
  }

  async providers(): Promise<ProvidersResponseWire> {
    return this.request<ProvidersResponseWire>("GET", "/providers");
  }

  private async request<T>(
    method: "GET" | "POST" | "PUT",
    path: string,
    body?: unknown,
    opts: { requireAuth?: boolean } = {}
  ): Promise<T> {
    const requireAuth = opts.requireAuth ?? true;
    const headers: Record<string, string> = {
      Accept: "application/json"
    };

    if (requireAuth) {
      const token = (await this.getToken())?.trim();
      if (!token) {
        throw new RuntimeClientError(
          "Local Runtime bearer token is not configured. Run 'Project T: Configure Local Runtime Token'.",
          401,
          "missing_token"
        );
      }
      headers.Authorization = `Bearer ${token}`;
    }

    let encodedBody: string | undefined;
    if (body !== undefined) {
      headers["Content-Type"] = "application/json";
      encodedBody = JSON.stringify(body);
    }

    const controller = new AbortController();
    const timer = setTimeout(() => controller.abort(), this.timeoutMs);

    try {
      const response = await this.fetchImpl(`${this.baseUrl}${path}`, {
        method,
        headers,
        body: encodedBody,
        signal: controller.signal
      });

      const rawText = await response.text();
      let parsed: unknown = undefined;
      if (rawText) {
        try {
          parsed = JSON.parse(rawText);
        } catch {
          parsed = undefined;
        }
      }

      if (!response.ok) {
        const errEnvelope = parsed as Partial<ErrorResponseWire> | undefined;
        const code = errEnvelope?.error?.code ?? `http_${response.status}`;
        const msg =
          errEnvelope?.error?.message ??
          `Local Runtime returned HTTP ${response.status} for ${path}`;
        throw new RuntimeClientError(msg, response.status, code);
      }

      return parsed as T;
    } catch (error) {
      if (error instanceof RuntimeClientError) {
        throw error;
      }
      if (error instanceof Error && error.name === "AbortError") {
        throw new RuntimeClientError(
          `Request to Local Runtime timed out after ${this.timeoutMs} ms`,
          504,
          "timeout"
        );
      }
      const message = error instanceof Error ? error.message : "Unknown network error";
      throw new RuntimeClientError(
        `Unable to reach Project T Local Runtime at ${this.baseUrl}: ${message}`,
        0,
        "connection_failed"
      );
    } finally {
      clearTimeout(timer);
    }
  }
}
