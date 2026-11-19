import assert from "node:assert/strict";
import { spawn } from "node:child_process";
import * as fs from "node:fs";
import * as http from "node:http";
import * as net from "node:net";
import * as os from "node:os";
import * as path from "node:path";
import { chromium } from "playwright";

const REPO_ROOT = path.resolve(import.meta.dirname, "..", "..");
const EXT_DIST = path.join(REPO_ROOT, "apps", "browser-extension", "dist");

function findFreePort() {
  return new Promise((resolve, reject) => {
    const server = net.createServer();
    server.listen(0, "127.0.0.1", () => {
      const addr = server.address();
      if (!addr || typeof addr === "string") {
        server.close();
        reject(new Error("Could not allocate free loopback port"));
        return;
      }
      const { port } = addr;
      server.close(() => resolve(port));
    });
    server.on("error", reject);
  });
}

function resolvePythonExecutable() {
  const winVenv = path.join(REPO_ROOT, ".venv", "Scripts", "python.exe");
  if (fs.existsSync(winVenv)) {
    return winVenv;
  }
  const unixVenv = path.join(REPO_ROOT, ".venv", "bin", "python");
  if (fs.existsSync(unixVenv)) {
    return unixVenv;
  }
  return process.env.PYTHON ?? "python";
}

function resolveChromiumExecutable() {
  if (process.env.PLAYWRIGHT_CHROMIUM_EXECUTABLE && fs.existsSync(process.env.PLAYWRIGHT_CHROMIUM_EXECUTABLE)) {
    return process.env.PLAYWRIGHT_CHROMIUM_EXECUTABLE;
  }
  try {
    const bundled = chromium.executablePath();
    if (bundled && fs.existsSync(bundled)) {
      return bundled;
    }
  } catch {
    // Fall back to system Chromium/Chrome/Edge if bundled Playwright binary is absent
  }
  const candidates = [
    "C:\\Program Files\\Google\\Chrome\\Application\\chrome.exe",
    "C:\\Program Files (x86)\\Microsoft\\Edge\\Application\\msedge.exe",
    "/usr/bin/chromium",
    "/usr/bin/chromium-browser",
    "/usr/bin/google-chrome"
  ];
  for (const candidate of candidates) {
    if (fs.existsSync(candidate)) {
      return candidate;
    }
  }
  return undefined;
}

async function waitForHealth(baseUrl, timeoutMs = 15_000) {
  const start = Date.now();
  while (Date.now() - start < timeoutMs) {
    try {
      const res = await fetch(`${baseUrl}/health`);
      if (res.ok) {
        return;
      }
    } catch {
      // Wait for uvicorn startup
    }
    await new Promise((r) => setTimeout(r, 150));
  }
  throw new Error(`Timed out waiting for Local Runtime health at ${baseUrl}`);
}

const FIXTURE_PAGES = {
  "/chatgpt.html": `<!doctype html>
<html data-project-t-site="chatgpt">
  <head><meta charset="utf-8" /><title>ChatGPT Fixture</title><link rel="stylesheet" href="/styles.css" /></head>
  <body>
    <form><div id="prompt-textarea" contenteditable="true"></div></form>
  </body>
</html>`,
  "/claude.html": `<!doctype html>
<html data-project-t-site="claude">
  <head><meta charset="utf-8" /><title>Claude Fixture</title><link rel="stylesheet" href="/styles.css" /></head>
  <body>
    <fieldset><div class="ProseMirror" contenteditable="true"></div></fieldset>
  </body>
</html>`,
  "/gemini.html": `<!doctype html>
<html data-project-t-site="gemini">
  <head><meta charset="utf-8" /><title>Gemini Fixture</title><link rel="stylesheet" href="/styles.css" /></head>
  <body>
    <rich-textarea><div class="ql-editor" contenteditable="true"></div></rich-textarea>
  </body>
</html>`
};

const MIME_BY_EXT = {
  ".html": "text/html; charset=utf-8",
  ".js": "application/javascript; charset=utf-8",
  ".css": "text/css; charset=utf-8",
  ".json": "application/json; charset=utf-8"
};

async function run() {
  assert.ok(fs.existsSync(path.join(EXT_DIST, "contentScript.js")), "Build apps/browser-extension first");

  const tempDir = fs.mkdtempSync(path.join(os.tmpdir(), "project-t-e2e-"));
  const dataDir = path.join(tempDir, "runtime-data");
  const apiPort = await findFreePort();
  const fixturePort = await findFreePort();
  const apiBaseUrl = `http://127.0.0.1:${apiPort}/api/v1`;
  const fixtureOrigin = `http://127.0.0.1:${fixturePort}`;

  const fixtureServer = http.createServer((req, res) => {
    const reqPath = (req.url ?? "/").split("?")[0];
    if (reqPath in FIXTURE_PAGES) {
      res.writeHead(200, { "Content-Type": "text/html; charset=utf-8" });
      res.end(FIXTURE_PAGES[reqPath]);
      return;
    }
    const cleanRel = reqPath.replace(/^\/+/, "");
    const candidate = path.resolve(EXT_DIST, cleanRel);
    if (candidate.startsWith(EXT_DIST) && fs.existsSync(candidate) && fs.statSync(candidate).isFile()) {
      const ext = path.extname(candidate);
      res.writeHead(200, { "Content-Type": MIME_BY_EXT[ext] ?? "application/octet-stream" });
      fs.createReadStream(candidate).pipe(res);
      return;
    }
    res.writeHead(404);
    res.end("Not found");
  });

  await new Promise((resolve) => fixtureServer.listen(fixturePort, "127.0.0.1", resolve));

  const bootstrapCode = `
import sys
import threading
from pathlib import Path
import uvicorn
from project_t_local_runtime import LocalRuntimeService, RuntimeConfig, create_app

cfg = RuntimeConfig(
    host="127.0.0.1",
    port=${apiPort},
    data_dir=Path(r"${dataDir.replace(/\\/g, "\\\\")}"),
    allowed_origins=("${fixtureOrigin}",),
    use_os_keyring=False,
    allow_tiktoken=False,
)
svc = LocalRuntimeService(config=cfg)
print(f"TOKEN_READY:{svc.credentials.bearer_token}", flush=True)
app = create_app(service=svc)
server = uvicorn.Server(uvicorn.Config(app, host="127.0.0.1", port=${apiPort}, log_level="error"))

def _shutdown_on_stdin_eof():
    try:
        sys.stdin.read()
    finally:
        server.should_exit = True

threading.Thread(target=_shutdown_on_stdin_eof, daemon=True).start()
server.run()
`;

  const pyExe = resolvePythonExecutable();
  const serverProc = spawn(pyExe, ["-c", bootstrapCode], {
    cwd: REPO_ROOT,
    env: {
      ...process.env,
      PYTHONPATH: [
        path.join(REPO_ROOT, "packages", "contracts", "src"),
        path.join(REPO_ROOT, "packages", "optimization-core", "src"),
        path.join(REPO_ROOT, "packages", "provider-adapters", "src"),
        path.join(REPO_ROOT, "apps", "local-runtime", "src")
      ].join(path.delimiter)
    }
  });

  let browser;
  try {
    const bearerToken = await new Promise((resolve, reject) => {
      const timer = setTimeout(() => reject(new Error("Timed out reading runtime token")), 15_000);
      let buf = "";
      serverProc.stdout.on("data", (c) => {
        buf += c.toString("utf-8");
        const m = buf.match(/TOKEN_READY:([^\r\n]+)/);
        if (m?.[1]) {
          clearTimeout(timer);
          resolve(m[1].trim());
        }
      });
      serverProc.stderr.on("data", (c) => {
        buf += c.toString("utf-8");
      });
      serverProc.once("exit", (code) => {
        clearTimeout(timer);
        reject(new Error(`Local runtime exited early (${code}): ${buf}`));
      });
    });

    await waitForHealth(apiBaseUrl);

    const execPath = resolveChromiumExecutable();
    browser = await chromium.launch({
      ...(execPath ? { executablePath: execPath } : {}),
      headless: true
    });

    const samplePrompt = [
      "Hello, could you please inspect verifyJwtToken in src/auth/jwt.py in order to fix auth errors?",
      "Repeated context paragraph detailing JWT signature rules across API endpoints.",
      "Repeated context paragraph detailing JWT signature rules across API endpoints.",
      "Do not change the database schema."
    ].join("\n\n");

    const siteCases = [
      { path: "/chatgpt.html", selector: "#prompt-textarea", siteId: "chatgpt" },
      { path: "/claude.html", selector: "div.ProseMirror", siteId: "claude" },
      { path: "/gemini.html", selector: "div.ql-editor", siteId: "gemini" }
    ];

    for (const site of siteCases) {
      const page = await browser.newPage();
      const pageErrors = [];
      page.on("pageerror", (err) => pageErrors.push(err.message));

      await page.goto(`${fixtureOrigin}${site.path}`);

      // Fill site editor paragraphs cleanly
      await page.evaluate(
        ({ selector, text }) => {
          const el = document.querySelector(selector);
          for (const line of text.split("\n")) {
            const p = document.createElement("p");
            p.textContent = line;
            el.appendChild(p);
          }
        },
        { selector: site.selector, text: samplePrompt }
      );

      // Expose real CORS-checked Local Runtime fetch bridge for contentScript.js
      await page.evaluate(
        ({ apiUrl, token }) => {
          window.__projectTOptimize = async ({ text, provider, model }) => {
            const res = await fetch(`${apiUrl}/optimize`, {
              method: "POST",
              headers: {
                "Content-Type": "application/json",
                Authorization: `Bearer ${token}`
              },
              body: JSON.stringify({
                content: text,
                provider,
                model,
                mode: "balanced",
                integration: "browser"
              })
            });
            const wire = await res.json();
            return {
              requestId: wire.request_id,
              originalContent: wire.original_content,
              optimizedContent: wire.optimized_content,
              originalTokens: wire.tokens.original,
              optimizedTokens: wire.tokens.optimized,
              tokensSaved: wire.tokens.saved,
              reductionPercentage: wire.tokens.reduction_percentage,
              validationPassed: wire.validation.passed,
              accuracy: wire.tokens.accuracy,
              methods: wire.optimization.methods,
              warnings: wire.warnings,
              durationMs: wire.duration_ms
            };
          };
        },
        { apiUrl: apiBaseUrl, token: bearerToken }
      );

      await page.addScriptTag({ path: path.join(EXT_DIST, "contentScript.js") });

      // 1. Trigger optimization via explicit button
      await page.click('[data-project-t="trigger"]');
      await page.waitForSelector('[data-project-t="overlay"]');

      const badgeText = await page.textContent('[data-project-t="accuracy-badge"]');
      assert.ok(badgeText === "Estimated count" || badgeText === "Exact count");

      const previewOptimized = await page.textContent('[data-project-t="optimized-preview"]');
      assert.ok(previewOptimized.includes("verifyJwtToken"));
      assert.ok(previewOptimized.includes("Do not change the database schema."));
      assert.ok(previewOptimized.length < samplePrompt.length);

      // 2. Click Accept -> verify editor DOM updates
      await page.click('[data-project-t="accept-btn"]');
      await page.waitForSelector('[data-project-t="restore-btn"]');
      const editorAfterAccept = await page.evaluate((sel) => {
        const el = document.querySelector(sel);
        return Array.from(el.querySelectorAll("p")).map((p) => p.textContent).join("\n");
      }, site.selector);
      assert.equal(editorAfterAccept, previewOptimized);

      // 3. Click Restore Original -> verify verbatim recovery
      await page.click('[data-project-t="restore-btn"]');
      const editorAfterRestore = await page.evaluate((sel) => {
        const el = document.querySelector(sel);
        return Array.from(el.querySelectorAll("p")).map((p) => p.textContent).join("\n");
      }, site.selector);
      assert.equal(editorAfterRestore, samplePrompt);
      assert.deepEqual(pageErrors, []);

      await page.close();
      console.log(`E2E passed for ${site.siteId} fixture.`);
    }

    // Verify React Popup & Options pages render cleanly with zero page errors
    for (const uiCheck of [
      { path: "/popup.html", expectedText: "Project T Token Optimizer" },
      { path: "/options.html", expectedText: "Project T Local Runtime Pairing" }
    ]) {
      const page = await browser.newPage();
      const pageErrors = [];
      page.on("pageerror", (err) => pageErrors.push(err.message));
      await page.goto(`${fixtureOrigin}${uiCheck.path}`);
      await page.waitForSelector("text=" + uiCheck.expectedText);
      assert.deepEqual(pageErrors, []);
      await page.close();
      console.log(`E2E UI render passed for ${uiCheck.path}.`);
    }
  } finally {
    if (browser) {
      await browser.close();
    }
    fixtureServer.close();
    if (serverProc.exitCode === null) {
      await new Promise((resolve) => {
        const timer = setTimeout(() => {
          serverProc.kill();
          resolve();
        }, 5000);
        serverProc.once("exit", () => {
          clearTimeout(timer);
          resolve();
        });
        serverProc.stdin.end();
      });
    }
    if (fs.existsSync(tempDir)) {
      fs.rmSync(tempDir, { recursive: true, force: true, maxRetries: 10, retryDelay: 100 });
    }
  }
}

run().catch((err) => {
  console.error(err);
  process.exit(1);
});
