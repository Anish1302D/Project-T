import * as fs from "node:fs";
import * as path from "node:path";
import { describe, expect, it } from "vitest";

const EXT_ROOT = path.resolve(__dirname, "..");

describe("Browser Extension Manifest V3 & Security Audit", () => {
  it("enforces minimal Manifest V3 permissions and strict host allowlist", () => {
    const manifest = JSON.parse(
      fs.readFileSync(path.join(EXT_ROOT, "manifest.json"), "utf-8")
    ) as {
      manifest_version: number;
      permissions: string[];
      host_permissions: string[];
      content_scripts: Array<{ matches: string[] }>;
    };

    expect(manifest.manifest_version).toBe(3);
    expect(manifest.permissions.sort()).toEqual(["activeTab", "storage"]);

    const forbiddenPermissions = ["cookies", "tabs", "webRequest", "webRequestBlocking", "<all_urls>"];
    for (const bad of forbiddenPermissions) {
      expect(manifest.permissions).not.toContain(bad);
      expect(manifest.host_permissions).not.toContain(bad);
    }

    expect(manifest.host_permissions.sort()).toEqual([
      "http://127.0.0.1:4765/*",
      "http://localhost:4765/*",
      "https://chat.openai.com/*",
      "https://chatgpt.com/*",
      "https://claude.ai/*",
      "https://gemini.google.com/*"
    ]);

    const contentMatches = manifest.content_scripts.flatMap((c) => c.matches).sort();
    expect(contentMatches).toEqual([
      "https://chat.openai.com/*",
      "https://chatgpt.com/*",
      "https://claude.ai/*",
      "https://gemini.google.com/*"
    ]);
  });

  it("contains zero hardcoded provider API keys or cookie reads across source and dist", () => {
    const srcRoot = path.join(EXT_ROOT, "src");
    const walk = (dir: string): string[] =>
      fs.readdirSync(dir, { withFileTypes: true }).flatMap((entry) => {
        const full = path.join(dir, entry.name);
        return entry.isDirectory() ? walk(full) : [full];
      });

    const files = walk(srcRoot).filter((f) => f.endsWith(".ts") || f.endsWith(".tsx"));
    const distDir = path.join(EXT_ROOT, "dist");
    if (fs.existsSync(distDir)) {
      files.push(
        ...walk(distDir).filter((f) => f.endsWith(".js") && !f.endsWith(".map"))
      );
    }

    for (const file of files) {
      const code = fs.readFileSync(file, "utf-8");
      expect(code).not.toMatch(/document\.cookie/);
      expect(code).not.toMatch(/sk-proj-[A-Za-z0-9_-]{10,}|AIza[A-Za-z0-9_-]{20,}/);
    }
  });
});
