import React, { useEffect, useState } from "react";
import type { HealthResponseWire } from "@project-t/contracts";
import type { BackgroundRequest, BackgroundResponse, ExtensionSettings } from "../shared/messages.js";

function sendRuntimeMessage<T>(req: BackgroundRequest): Promise<BackgroundResponse<T>> {
  return new Promise((resolve) => {
    if (typeof chrome === "undefined" || !chrome.runtime?.sendMessage) {
      resolve({ ok: false, error: "Chrome extension runtime unavailable in standalone preview." });
      return;
    }
    chrome.runtime.sendMessage(req, (resp: BackgroundResponse<T>) => {
      if (chrome.runtime.lastError) {
        resolve({ ok: false, error: chrome.runtime.lastError.message ?? "Runtime error" });
        return;
      }
      resolve(resp ?? { ok: false, error: "Empty response" });
    });
  });
}

export function PopupApp(): React.ReactElement {
  const [health, setHealth] = useState<HealthResponseWire | null>(null);
  const [settings, setSettings] = useState<ExtensionSettings | null>(null);
  const [statusMessage, setStatusMessage] = useState<string>("");

  useEffect(() => {
    void (async () => {
      const [hRes, sRes] = await Promise.all([
        sendRuntimeMessage<HealthResponseWire>({ type: "PROJECT_T_HEALTH" }),
        sendRuntimeMessage<ExtensionSettings>({ type: "PROJECT_T_GET_SETTINGS" })
      ]);
      if (hRes.ok) {
        setHealth(hRes.data);
      } else {
        setStatusMessage(hRes.error);
      }
      if (sRes.ok) {
        setSettings(sRes.data);
      }
    })();
  }, []);

  const triggerActiveTab = (type: "PROJECT_T_TRIGGER_OPTIMIZE" | "PROJECT_T_RESTORE_ORIGINAL") => {
    if (typeof chrome === "undefined" || !chrome.tabs?.query) {
      setStatusMessage("Active tab API unavailable outside browser extension.");
      return;
    }
    chrome.tabs.query({ active: true, currentWindow: true }, (tabs) => {
      const tabId = tabs[0]?.id;
      if (tabId === undefined) {
        setStatusMessage("No active tab selected.");
        return;
      }
      chrome.tabs.sendMessage(tabId, { type }, (resp) => {
        if (chrome.runtime.lastError) {
          setStatusMessage("Open ChatGPT, Claude, or Gemini to optimize active prompt.");
          return;
        }
        setStatusMessage(
          resp?.ok
            ? type === "PROJECT_T_RESTORE_ORIGINAL"
              ? "Restored original prompt."
              : "Preview opened on page."
            : resp?.error ?? "Action could not complete."
        );
      });
    });
  };

  const openOptions = () => {
    if (typeof chrome !== "undefined" && chrome.runtime?.openOptionsPage) {
      chrome.runtime.openOptionsPage();
    }
  };

  return (
    <div>
      <div className="pt-review-header">
        <strong>Project T Token Optimizer</strong>
        <span className="pt-badge">
          {health?.status === "ok" ? `Local v${health.version}` : "Offline"}
        </span>
      </div>

      <p>
        Mode: <code>{settings?.mode ?? "balanced"}</code> • Token:{" "}
        <code>{settings?.bearerToken ? "Configured" : "Missing"}</code>
      </p>

      <div className="pt-actions">
        <button
          type="button"
          className="pt-btn pt-btn-primary"
          onClick={() => triggerActiveTab("PROJECT_T_TRIGGER_OPTIMIZE")}
        >
          Optimize Active Prompt
        </button>
        <button
          type="button"
          className="pt-btn"
          onClick={() => triggerActiveTab("PROJECT_T_RESTORE_ORIGINAL")}
        >
          Restore Original
        </button>
        <button type="button" className="pt-btn" onClick={openOptions}>
          Options
        </button>
      </div>

      {statusMessage && <p>{statusMessage}</p>}
    </div>
  );
}
