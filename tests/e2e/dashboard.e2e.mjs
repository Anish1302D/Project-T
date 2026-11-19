import assert from "node:assert/strict";
import { spawn } from "node:child_process";
import * as fs from "node:fs";
import * as http from "node:http";
import * as net from "node:net";
import * as os from "node:os";
import * as path from "node:path";
import { chromium } from "playwright";

const REPO_ROOT = path.resolve(import.meta.dirname, "..", "..");
const DASHBOARD_DIST = path.join(REPO_ROOT, "apps", "dashboard", "dist");

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
  if (
    process.env.PLAYWRIGHT_CHROMIUM_EXECUTABLE &&
    fs.existsSync(process.env.PLAYWRIGHT_CHROMIUM_EXECUTABLE)
  ) {
    return process.env.PLAYWRIGHT_CHROMIUM_EXECUTABLE;
  }
  try {
    const bundled = chromium.executablePath();
    if (bundled && fs.existsSync(bundled)) {
      return bundled;
    }
  } catch {
    // Fall back to system Chrome/Edge when Playwright binary is absent
  }
  for (const candidate of [
    "C:\\Program Files\\Google\\Chrome\\Application\\chrome.exe",
    "C:\\Program Files (x86)\\Microsoft\\Edge\\Application\\msedge.exe",
    "/usr/bin/chromium",
    "/usr/bin/chromium-browser",
    "/usr/bin/google-chrome"
  ]) {
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
      // Wait for control-plane startup
    }
    await new Promise((r) => setTimeout(r, 150));
  }
  throw new Error(`Timed out waiting for Control Plane health at ${baseUrl}`);
}

function startStaticDashboardServer(port) {
  const mimeTypes = {
    ".html": "text/html; charset=utf-8",
    ".js": "application/javascript; charset=utf-8",
    ".css": "text/css; charset=utf-8",
    ".svg": "image/svg+xml"
  };

  return new Promise((resolve) => {
    const server = http.createServer((req, res) => {
      const cleanUrl = (req.url ?? "/").split("?")[0];
      const relPath = cleanUrl === "/" ? "index.html" : cleanUrl.replace(/^\/+/, "");
      const target = path.join(DASHBOARD_DIST, relPath);
      const fileToServe = fs.existsSync(target) && fs.statSync(target).isFile()
        ? target
        : path.join(DASHBOARD_DIST, "index.html");
      const ext = path.extname(fileToServe);
      res.writeHead(200, { "Content-Type": mimeTypes[ext] ?? "application/octet-stream" });
      res.end(fs.readFileSync(fileToServe));
    });
    server.listen(port, "127.0.0.1", () => resolve(server));
  });
}

async function seedCloudControlPlane(cloudUrl) {
  const regRes = await fetch(`${cloudUrl}/api/cloud/v1/auth/register`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({
      email: "e2e@project-t.local",
      display_name: "E2E User",
      password: "e2e-password-123"
    })
  });
  assert.equal(regRes.status, 201);
  const { access_token: token } = await regRes.json();
  const headers = {
    "Content-Type": "application/json",
    Authorization: `Bearer ${token}`
  };

  await fetch(`${cloudUrl}/api/cloud/v1/auth/devices/pair`, {
    method: "POST",
    headers,
    body: JSON.stringify({
      installation_id: "inst_laptop",
      device_id: "dev_laptop",
      device_label: "Laptop-VSCode",
      os_platform: "Windows 11",
      sync_enabled: true
    })
  });

  await fetch(`${cloudUrl}/api/cloud/v1/auth/devices/pair`, {
    method: "POST",
    headers,
    body: JSON.stringify({
      installation_id: "inst_server",
      device_id: "dev_server",
      device_label: "Gateway-Box",
      os_platform: "Linux",
      sync_enabled: true
    })
  });

  const syncLaptop = await fetch(`${cloudUrl}/api/cloud/v1/sync/runs`, {
    method: "POST",
    headers,
    body: JSON.stringify({
      installation_id: "inst_laptop",
      runs: [
        {
          run_id: "r1",
          request_id: "req_1",
          provider: "openai",
          model: "gpt-4o",
          integration: "vscode",
          content_type: "prompt",
          optimization_mode: "balanced",
          status: "validated",
          methods: ["whitespace_normalization", "exact_paragraph_dedup"],
          warnings: [],
          quality_score: 0.94,
          duration_ms: 4,
          original_tokens: 400,
          optimized_tokens: 260,
          tokens_saved: 140,
          reduction_percentage: 35.0,
          accuracy: "exact",
          pricing_version: "2026-11-v1",
          estimated_cost_avoided_usd: 0.00035,
          created_at: "2026-11-18T09:00:00Z"
        },
        {
          run_id: "r2",
          request_id: "req_2",
          provider: "anthropic",
          model: "claude-sonnet-4",
          integration: "browser",
          content_type: "prompt",
          optimization_mode: "safe",
          status: "validated",
          methods: ["filler_phrase_trim"],
          warnings: [],
          quality_score: 0.91,
          duration_ms: 6,
          original_tokens: 300,
          optimized_tokens: 210,
          tokens_saved: 90,
          reduction_percentage: 30.0,
          accuracy: "estimated",
          pricing_version: "2026-11-v1",
          estimated_cost_avoided_usd: 0.00027,
          created_at: "2026-11-19T08:00:00Z"
        }
      ]
    })
  });
  assert.equal(syncLaptop.status, 200);

  const syncServer = await fetch(`${cloudUrl}/api/cloud/v1/sync/runs`, {
    method: "POST",
    headers,
    body: JSON.stringify({
      installation_id: "inst_server",
      runs: [
        {
          run_id: "r3",
          request_id: "req_3",
          provider: "google",
          model: "gemini-2.5-pro",
          integration: "gateway",
          content_type: "prompt",
          optimization_mode: "balanced",
          status: "validated",
          methods: ["exact_paragraph_dedup"],
          warnings: [],
          quality_score: 0.95,
          duration_ms: 9,
          original_tokens: 500,
          optimized_tokens: 350,
          tokens_saved: 150,
          reduction_percentage: 30.0,
          accuracy: "exact",
          provider_confirmed_original_tokens: 495,
          provider_confirmed_input_tokens: 345,
          pricing_version: "2026-11-v1",
          estimated_cost_avoided_usd: 0.000188,
          provider_confirmed_cost_avoided_usd: 0.000188,
          created_at: "2026-11-19T11:00:00Z"
        }
      ]
    })
  });
  assert.equal(syncServer.status, 200);

  const benchRes = await fetch(`${cloudUrl}/api/cloud/v1/sync/benchmarks`, {
    method: "POST",
    headers,
    body: JSON.stringify({
      installation_id: "inst_server",
      results: [
        {
          id: "bench_prompt_e2e",
          suite_name: "core-v1",
          category: "prompt",
          dataset_version: "2026-11-v1",
          engine_version: "0.5.0",
          provider: "openai",
          model: "gpt-4o",
          optimization_mode: "balanced",
          sample_count: 5,
          unit_test_pass_rate: 1.0,
          constraint_preservation_rate: 1.0,
          identifier_preservation_rate: 1.0,
          median_reduction_pct: 45.95,
          p50_latency_ms: 1.29,
          p95_latency_ms: 3.46,
          negative_savings_count: 2
        }
      ]
    })
  });
  assert.equal(benchRes.status, 200);

  return token;
}

async function run() {
  assert.ok(
    fs.existsSync(path.join(DASHBOARD_DIST, "index.html")),
    "apps/dashboard/dist/index.html missing; run pnpm turbo run build first"
  );

  const cloudPort = await findFreePort();
  const webPort = await findFreePort();
  const cloudUrl = `http://127.0.0.1:${cloudPort}`;
  const webUrl = `http://127.0.0.1:${webPort}`;
  const tmpDir = fs.mkdtempSync(path.join(os.tmpdir(), "project-t-dashboard-e2e-"));
  const dbPath = path.join(tmpDir, "cloud_e2e.db");

  const pyExe = resolvePythonExecutable();
  const runnerScript = [
    "import sys, threading, uvicorn",
    "from pathlib import Path",
    "from project_t_cloud_services import CloudConfig, create_control_plane_app",
    `cfg = CloudConfig(host='127.0.0.1', port=${cloudPort}, data_dir=Path(${JSON.stringify(tmpDir)}), database_url='sqlite:///' + ${JSON.stringify(dbPath.replace(/\\/g, "/"))}, jwt_secret='e2e-dashboard-jwt-secret-key-32bytes', allowed_origins=('http://127.0.0.1:${webPort}', 'http://localhost:${webPort}'))`,
    "app = create_control_plane_app(cfg)",
    `server = uvicorn.Server(uvicorn.Config(app, host='127.0.0.1', port=${cloudPort}, log_level='error'))`,
    "def _watch():",
    "    sys.stdin.read()",
    "    server.should_exit = True",
    "threading.Thread(target=_watch, daemon=True).start()",
    "server.run()"
  ].join("\n");

  const cloudProc = spawn(pyExe, ["-c", runnerScript], {
    cwd: REPO_ROOT,
    stdio: ["pipe", "pipe", "pipe"]
  });

  let webServer;
  let browser;
  try {
    await waitForHealth(cloudUrl);
    const accessToken = await seedCloudControlPlane(cloudUrl);
    webServer = await startStaticDashboardServer(webPort);

    const execPath = resolveChromiumExecutable();
    browser = await chromium.launch({
      headless: true,
      ...(execPath ? { executablePath: execPath } : {})
    });
    const page = await browser.newPage();
    const pageErrors = [];
    page.on("pageerror", (err) => pageErrors.push(err.message));

    await page.goto(
      `${webUrl}/?api=${encodeURIComponent(cloudUrl)}&token=${encodeURIComponent(accessToken)}`,
      { waitUntil: "networkidle" }
    );

    await page.waitForFunction(
      () =>
        document.querySelector('[data-testid="data-source-badge"]')?.textContent?.includes(
          "Live Control Plane"
        ) ?? false
    );

    const expectedViews = [
      "view-original-vs-optimized",
      "view-net-tokens-saved",
      "view-cost-avoided",
      "view-provider-model",
      "view-integration-breakdown",
      "view-usage-trends",
      "view-modes-methods",
      "view-validation-fallbacks",
      "view-benchmark-summaries",
      "view-latency-percentiles"
    ];

    for (const viewId of expectedViews) {
      const visible = await page.isVisible(`[data-testid="${viewId}"]`);
      assert.equal(visible, true, `Expected view ${viewId} to be visible`);
    }

    assert.equal(await page.textContent('[data-testid="device-count"]'), "2");
    assert.equal(await page.textContent('[data-testid="metric-original-tokens"]'), "1,200");
    assert.equal(await page.textContent('[data-testid="metric-net-saved"]'), "380");
    assert.equal(await page.textContent('[data-testid="metric-exact-saved"]'), "290");
    assert.equal(await page.textContent('[data-testid="metric-estimated-saved"]'), "90");

    // Interactive filtering: select provider='anthropic' and verify live rollup updates
    await page.selectOption('[data-testid="filter-provider"]', "anthropic");
    await page.waitForFunction(
      () => document.querySelector('[data-testid="metric-original-tokens"]')?.textContent === "300"
    );
    assert.equal(await page.textContent('[data-testid="metric-net-saved"]'), "90");

    // Switch granularity to weekly and reset filters
    await page.selectOption('[data-testid="filter-granularity"]', "weekly");
    await page.waitForFunction(
      () =>
        document
          .querySelector('[data-testid="view-usage-trends"]')
          ?.textContent?.includes("(weekly)") ?? false
    );

    await page.click('[data-testid="filter-reset"]');
    await page.waitForFunction(
      () => document.querySelector('[data-testid="metric-original-tokens"]')?.textContent === "1,200"
    );

    assert.deepEqual(pageErrors, [], `Unexpected page errors: ${pageErrors.join("; ")}`);
    console.log("Dashboard E2E passed: all 10 views rendered and interactive filters verified.");
  } finally {
    if (browser) {
      await browser.close();
    }
    if (webServer) {
      await new Promise((resolve) => webServer.close(resolve));
    }
    if (cloudProc && cloudProc.exitCode === null) {
      cloudProc.stdin?.end();
      await new Promise((resolve) => {
        const timer = setTimeout(() => {
          cloudProc.kill("SIGKILL");
          resolve();
        }, 5000);
        cloudProc.once("exit", () => {
          clearTimeout(timer);
          resolve();
        });
      });
    }
    fs.rmSync(tmpDir, { recursive: true, force: true, maxRetries: 10, retryDelay: 100 });
  }
}

await run();
