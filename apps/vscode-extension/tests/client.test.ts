import { describe, expect, it, vi } from "vitest";
import {
  LocalRuntimeClient,
  RuntimeClientError,
  isLoopbackUrl
} from "../src/runtime/client.js";

describe("LocalRuntimeClient", () => {
  it("accepts loopback URLs and rejects non-loopback runtime URLs by default", () => {
    expect(isLoopbackUrl("http://127.0.0.1:4765/api/v1")).toBe(true);
    expect(isLoopbackUrl("http://localhost:4765/api/v1")).toBe(true);
    expect(isLoopbackUrl("http://0.0.0.0:4765/api/v1")).toBe(false);
    expect(isLoopbackUrl("https://remote.example.com/api/v1")).toBe(false);

    expect(
      () =>
        new LocalRuntimeClient({
          baseUrl: "http://0.0.0.0:4765/api/v1",
          getToken: async () => "tok"
        })
    ).toThrowError(RuntimeClientError);
  });

  it("throws missing_token error when SecretStorage has no token for protected endpoints", async () => {
    const client = new LocalRuntimeClient({
      getToken: async () => undefined,
      fetchImpl: vi.fn() as unknown as typeof fetch
    });

    await expect(
      client.optimize({ content: "Hello world" })
    ).rejects.toMatchObject({
      statusCode: 401,
      errorCode: "missing_token"
    });
  });

  it("allows unauthenticated /health and validates /optimize wire contracts", async () => {
    const mockFetch = vi.fn(async (input: RequestInfo | URL, init?: RequestInit) => {
      const url = String(input);
      if (url.endsWith("/health")) {
        expect((init?.headers as Record<string, string>)?.Authorization).toBeUndefined();
        return new Response(
          JSON.stringify({
            status: "ok",
            version: "0.2.0",
            engine_ready: true,
            sqlite_ready: true
          }),
          { status: 200 }
        );
      }

      expect((init?.headers as Record<string, string>)?.Authorization).toBe("Bearer secret-tok");
      return new Response(
        JSON.stringify({
          request_id: "req_123",
          original_content: "Original prompt text",
          optimized_content: "Optimized text",
          tokens: {
            original: 20,
            optimized: 12,
            saved: 8,
            reduction_percentage: 40.0,
            accuracy: "estimated"
          },
          validation: {
            passed: true,
            constraints_preserved: true,
            identifiers_preserved: true,
            structure_preserved: true,
            quality_score: 0.98
          },
          optimization: {
            methods: ["rule_based_compression"],
            mode: "balanced"
          },
          duration_ms: 4,
          warnings: []
        }),
        { status: 200 }
      );
    });

    const client = new LocalRuntimeClient({
      getToken: async () => "secret-tok",
      fetchImpl: mockFetch as unknown as typeof fetch
    });

    const health = await client.health();
    expect(health.status).toBe("ok");

    const { result } = await client.optimize({ content: "Original prompt text" });
    expect(result.tokensSaved).toBe(8);
    expect(result.accuracy).toBe("estimated");
  });

  it("redacts secrets in HTTP error messages", async () => {
    const mockFetch = vi.fn(async () => {
      return new Response(
        JSON.stringify({
          error: {
            code: "unauthorized",
            message: "Failed auth for Bearer super_secret_token_abc123"
          }
        }),
        { status: 401 }
      );
    });

    const client = new LocalRuntimeClient({
      getToken: async () => "super_secret_token_abc123",
      fetchImpl: mockFetch as unknown as typeof fetch
    });

    await expect(client.metrics()).rejects.toMatchObject({
      statusCode: 401,
      errorCode: "unauthorized",
      message: expect.not.stringContaining("super_secret_token_abc123")
    });
  });
});
