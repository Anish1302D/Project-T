import * as fs from "node:fs";
import * as path from "node:path";
import { build } from "esbuild";

const rootDir = path.resolve(import.meta.dirname, "..");
const distDir = path.join(rootDir, "dist");

fs.rmSync(distDir, { recursive: true, force: true });
fs.mkdirSync(distDir, { recursive: true });

// 1. Background service worker (ESM)
await build({
  entryPoints: [path.join(rootDir, "src", "background", "serviceWorker.ts")],
  bundle: true,
  format: "esm",
  platform: "browser",
  target: "chrome120",
  outfile: path.join(distDir, "serviceWorker.js"),
  sourcemap: true
});

// 2. Content script (self-contained IIFE for Chrome MV3 content_scripts isolation)
await build({
  entryPoints: [path.join(rootDir, "src", "content", "contentScript.ts")],
  bundle: true,
  format: "iife",
  platform: "browser",
  target: "chrome120",
  outfile: path.join(distDir, "contentScript.js"),
  sourcemap: true
});

// 3. Popup and Options React UIs (ESM)
await build({
  entryPoints: [
    path.join(rootDir, "src", "popup", "main.tsx"),
    path.join(rootDir, "src", "options", "main.tsx")
  ],
  bundle: true,
  format: "esm",
  platform: "browser",
  target: "chrome120",
  outdir: distDir,
  entryNames: "[dir]",
  sourcemap: true
});

for (const staticFile of ["manifest.json", "popup.html", "options.html", "styles.css"]) {
  fs.copyFileSync(path.join(rootDir, staticFile), path.join(distDir, staticFile));
}

console.log("Built @project-t/browser-extension into dist/");
