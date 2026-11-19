// @vitest-environment jsdom
import { describe, expect, it, vi } from "vitest";
import { chatGptAdapter } from "../src/integrations/chatgpt.js";
import { claudeAdapter } from "../src/integrations/claude.js";
import { geminiAdapter } from "../src/integrations/gemini.js";
import { resolveSiteAdapterByHostname } from "../src/integrations/registry.js";

describe("Browser Extension SiteAdapters (DOM fixtures)", () => {
  it("resolves adapters strictly for supported hostnames", () => {
    expect(resolveSiteAdapterByHostname("chatgpt.com")?.id).toBe("chatgpt");
    expect(resolveSiteAdapterByHostname("chat.openai.com")?.id).toBe("chatgpt");
    expect(resolveSiteAdapterByHostname("claude.ai")?.id).toBe("claude");
    expect(resolveSiteAdapterByHostname("gemini.google.com")?.id).toBe("gemini");
    expect(resolveSiteAdapterByHostname("example.com")).toBeNull();
  });

  it("extracts and writes ChatGPT ProseMirror/textarea prompts and fires input events", () => {
    document.body.innerHTML = `<form><div id="prompt-textarea" contenteditable="true"><p>Hello ChatGPT</p><p>Second line</p></div></form>`;
    const input = chatGptAdapter.findPromptInput(document);
    expect(input).not.toBeNull();
    expect(chatGptAdapter.readPromptText(input!)).toBe("Hello ChatGPT\nSecond line");

    const onInput = vi.fn();
    input!.addEventListener("input", onInput);
    const written = chatGptAdapter.writePromptText(input!, "Optimized line 1\nOptimized line 2");
    expect(written).toBe(true);
    expect(onInput).toHaveBeenCalledTimes(1);
    expect(chatGptAdapter.readPromptText(input!)).toBe("Optimized line 1\nOptimized line 2");
  });

  it("extracts and writes Claude ProseMirror prompts", () => {
    document.body.innerHTML = `<fieldset><div class="ProseMirror" contenteditable="true"><p>Claude prompt text</p></div></fieldset>`;
    const input = claudeAdapter.findPromptInput(document);
    expect(input).not.toBeNull();
    expect(claudeAdapter.readPromptText(input!)).toBe("Claude prompt text");
    expect(claudeAdapter.writePromptText(input!, "Concise Claude prompt")).toBe(true);
    expect(claudeAdapter.readPromptText(input!)).toBe("Concise Claude prompt");
  });

  it("extracts and writes Gemini Quill rich-textarea prompts", () => {
    document.body.innerHTML = `<rich-textarea><div class="ql-editor" contenteditable="true"><p>Gemini prompt text</p></div></rich-textarea>`;
    const input = geminiAdapter.findPromptInput(document);
    expect(input).not.toBeNull();
    expect(geminiAdapter.readPromptText(input!)).toBe("Gemini prompt text");
    expect(geminiAdapter.writePromptText(input!, "Concise Gemini prompt")).toBe(true);
    expect(geminiAdapter.readPromptText(input!)).toBe("Concise Gemini prompt");
  });

  it("refuses password inputs even if matching generic selectors", () => {
    document.body.innerHTML = `<form><input id="prompt-textarea" type="password" value="secret123" /></form>`;
    expect(chatGptAdapter.findPromptInput(document)).toBeNull();
  });
});
