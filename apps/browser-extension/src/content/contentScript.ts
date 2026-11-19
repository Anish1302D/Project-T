import {
  resolveSiteAdapterByHostname,
  resolveSiteAdapterById
} from "../integrations/registry.js";
import type {
  BackgroundRequest,
  BackgroundResponse,
  ContentScriptRequest,
  OptimizeTextResponseData
} from "../shared/messages.js";
import { BrowserPromptController } from "./controller.js";

function resolveCurrentAdapter(doc: Document) {
  const hostAdapter = resolveSiteAdapterByHostname(doc.location?.hostname ?? "");
  if (hostAdapter) {
    return hostAdapter;
  }
  // Allow explicit fixture test harnesses to declare a supported site ID
  const declaredSite = doc.documentElement?.getAttribute("data-project-t-site");
  return declaredSite ? resolveSiteAdapterById(declaredSite) : null;
}

function sendBackgroundOptimize(params: {
  text: string;
  siteId: "chatgpt" | "claude" | "gemini";
  provider: string;
  model: string;
}) {
  return new Promise<OptimizeTextResponseData["result"]>((resolve, reject) => {
    const req: BackgroundRequest = {
      type: "PROJECT_T_OPTIMIZE_TEXT",
      payload: params
    };

    if (typeof chrome !== "undefined" && chrome.runtime?.sendMessage) {
      chrome.runtime.sendMessage(req, (resp: BackgroundResponse<OptimizeTextResponseData>) => {
        if (chrome.runtime.lastError) {
          reject(new Error(chrome.runtime.lastError.message));
          return;
        }
        if (!resp?.ok) {
          reject(new Error(resp?.error ?? "Unknown Local Runtime error"));
          return;
        }
        resolve(resp.data.result);
      });
      return;
    }

    // Optional test bridge hook injected in headless fixture E2E environments
    const testBridge = (window as unknown as {
      __projectTOptimize?: typeof sendBackgroundOptimize;
    }).__projectTOptimize;
    if (testBridge) {
      void testBridge(params).then(resolve, reject);
      return;
    }

    reject(new Error("Project T background service worker unavailable."));
  });
}

function bootstrap(): void {
  const adapter = resolveCurrentAdapter(document);
  if (!adapter) {
    return;
  }

  const controller = new BrowserPromptController({
    doc: document,
    adapter,
    optimizePrompt: sendBackgroundOptimize
  });
  controller.mount();

  if (typeof chrome !== "undefined" && chrome.runtime?.onMessage) {
    chrome.runtime.onMessage.addListener(
      (msg: ContentScriptRequest, _sender, sendResponse) => {
        if (msg.type === "PROJECT_T_TRIGGER_OPTIMIZE") {
          void controller
            .triggerOptimize()
            .then((result) => sendResponse({ ok: true, result }))
            .catch((err) =>
              sendResponse({
                ok: false,
                error: err instanceof Error ? err.message : String(err)
              })
            );
          return true;
        }
        if (msg.type === "PROJECT_T_RESTORE_ORIGINAL") {
          const restored = controller.restoreOriginal();
          sendResponse({ ok: restored });
          return false;
        }
        if (msg.type === "PROJECT_T_GET_STATUS") {
          sendResponse({
            ok: true,
            siteId: adapter.id,
            canRestore: controller.getLastApplied() !== null
          });
          return false;
        }
        return false;
      }
    );
  }
}

bootstrap();
