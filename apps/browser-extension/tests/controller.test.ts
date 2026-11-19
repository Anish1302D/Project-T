// @vitest-environment jsdom
import { describe, expect, it, vi } from "vitest";
import {
  BridgeError,
  optimizePromptViaRuntime
} from "../src/background/runtimeBridge.js";
import { BrowserPromptController } from "../src/content/controller.js";
import { chatGptAdapter } from "../src/integrations/chatgpt.js";
import { DEFAULT_EXTENSION_SETTINGS } from "../src/shared/messages.js";

describe("BrowserPromptController & RuntimeBridge", () => {
  it("supports explicit trigger -> preview -> accept -> restore flow", async () => {
    document.body.innerHTML = `<form><textarea id="prompt-textarea">Hello, could you please fix auth?</textarea></form>`;

    const controller = new BrowserPromptController({
      doc: document,
      adapter: chatGptAdapter,
      optimizePrompt: async ({ text }) => ({
        requestId: "req_browser_1",
        originalContent: text,
        optimizedContent: "Fix auth.",
        originalTokens: 10,
        optimizedTokens: 3,
        tokensSaved: 7,
        reductionPercentage: 70.0,
        validationPassed: true,
        accuracy: "estimated",
        methods: ["rule_based_compression"],
        warnings: [],
        durationMs: 2
      })
    });

    controller.mount();
    const trigger = document.querySelector('[data-project-t="trigger"]') as HTMLButtonElement;
    expect(trigger).not.toBeNull();

    await controller.triggerOptimize();
    const badge = document.querySelector('[data-project-t="accuracy-badge"]');
    expect(badge?.textContent).toBe("Estimated count");
    expect(
      document.querySelector('[data-project-t="optimized-preview"]')?.textContent
    ).toBe("Fix auth.");

    const accepted = await controller.acceptPending();
    expect(accepted).toBe(true);
    const textarea = document.getElementById("prompt-textarea") as HTMLTextAreaElement;
    expect(textarea.value).toBe("Fix auth.");

    const restored = controller.restoreOriginal();
    expect(restored).toBe(true);
    expect(textarea.value).toBe("Hello, could you please fix auth?");
  });

  it("handles reject cleanly and falls back to clipboard when editor blocks write", async () => {
    document.body.innerHTML = `<div id="prompt-textarea" contenteditable="true"><p>Original text</p></div>`;
    const copyMock = vi.fn(async () => true);

    const blockingAdapter = {
      ...chatGptAdapter,
      writePromptText: () => false
    };

    const controller = new BrowserPromptController({
      doc: document,
      adapter: blockingAdapter,
      copyToClipboard: copyMock,
      optimizePrompt: async ({ text }) => ({
        requestId: "req_browser_2",
        originalContent: text,
        optimizedContent: "Shorter",
        originalTokens: 5,
        optimizedTokens: 2,
        tokensSaved: 3,
        reductionPercentage: 60.0,
        validationPassed: true,
        accuracy: "exact",
        methods: ["rule_based_compression"],
        warnings: [],
        durationMs: 1
      })
    });

    await controller.triggerOptimize();
    const applied = await controller.acceptPending();
    expect(applied).toBe(false);
    expect(copyMock).toHaveBeenCalledWith("Shorter");

    await controller.triggerOptimize();
    controller.rejectPending();
    expect(document.querySelector('[data-project-t="overlay"]')).toBeNull();
  });

  it("enforces loopback URLs, requires bearer token, and redacts secrets on error", async () => {
    await expect(
      optimizePromptViaRuntime(
        {
          ...DEFAULT_EXTENSION_SETTINGS,
          runtimeUrl: "https://remote.example.com/api/v1",
          bearerToken: "tok"
        },
        { text: "hello" }
      )
    ).rejects.toThrowError(BridgeError);

    await expect(
      optimizePromptViaRuntime(
        { ...DEFAULT_EXTENSION_SETTINGS, bearerToken: "" },
        { text: "hello" }
      )
    ).rejects.toMatchObject({ code: "missing_token" });

    const badFetch = vi.fn(async () => {
      return new Response(
        JSON.stringify({
          error: { code: "unauthorized", message: "Bad token Bearer top_secret_tok_999" }
        }),
        { status: 401 }
      );
    });

    await expect(
      optimizePromptViaRuntime(
        { ...DEFAULT_EXTENSION_SETTINGS, bearerToken: "top_secret_tok_999" },
        { text: "hello" },
        badFetch as unknown as typeof fetch
      )
    ).rejects.toMatchObject({
      code: "unauthorized",
      message: expect.not.stringContaining("top_secret_tok_999")
    });
  });
});
