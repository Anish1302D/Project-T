import type {
  BackgroundRequest,
  BackgroundResponse
} from "../shared/messages.js";
import {
  loadExtensionSettings,
  saveExtensionSettings
} from "../shared/storage.js";
import {
  BridgeError,
  checkRuntimeHealth,
  isLoopbackRuntimeUrl,
  optimizePromptViaRuntime
} from "./runtimeBridge.js";

export async function handleBackgroundMessage(
  msg: BackgroundRequest
): Promise<BackgroundResponse> {
  try {
    if (msg.type === "PROJECT_T_GET_SETTINGS") {
      const settings = await loadExtensionSettings();
      return { ok: true, data: settings };
    }

    if (msg.type === "PROJECT_T_SAVE_SETTINGS") {
      if (msg.payload.runtimeUrl && !isLoopbackRuntimeUrl(msg.payload.runtimeUrl)) {
        return {
          ok: false,
          error: "Runtime URL must target loopback 127.0.0.1 or localhost.",
          code: "non_loopback_url"
        };
      }
      const saved = await saveExtensionSettings(msg.payload);
      return { ok: true, data: saved };
    }

    const settings = await loadExtensionSettings();

    if (msg.type === "PROJECT_T_HEALTH") {
      const health = await checkRuntimeHealth(settings);
      return { ok: true, data: health };
    }

    if (msg.type === "PROJECT_T_OPTIMIZE_TEXT") {
      const result = await optimizePromptViaRuntime(settings, {
        text: msg.payload.text,
        provider: msg.payload.provider,
        model: msg.payload.model
      });
      return { ok: true, data: { result } };
    }

    return { ok: false, error: "Unsupported message type.", code: "unsupported_message" };
  } catch (err) {
    if (err instanceof BridgeError) {
      return { ok: false, error: err.message, code: err.code };
    }
    return {
      ok: false,
      error: err instanceof Error ? err.message : "Unknown extension runtime error"
    };
  }
}

if (typeof chrome !== "undefined" && chrome.runtime?.onMessage) {
  chrome.runtime.onMessage.addListener(
    (message: BackgroundRequest, _sender, sendResponse) => {
      void handleBackgroundMessage(message).then(sendResponse);
      return true;
    }
  );
}
