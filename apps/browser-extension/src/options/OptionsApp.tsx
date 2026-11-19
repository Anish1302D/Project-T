import React, { useEffect, useState } from "react";
import type { OptimizationMode } from "@project-t/contracts";
import {
  DEFAULT_EXTENSION_SETTINGS,
  type BackgroundRequest,
  type BackgroundResponse,
  type ExtensionSettings
} from "../shared/messages.js";

function sendMessage<T>(req: BackgroundRequest): Promise<BackgroundResponse<T>> {
  return new Promise((resolve) => {
    if (typeof chrome === "undefined" || !chrome.runtime?.sendMessage) {
      resolve({ ok: false, error: "Extension background unavailable." });
      return;
    }
    chrome.runtime.sendMessage(req, (resp: BackgroundResponse<T>) => {
      resolve(resp ?? { ok: false, error: "Empty response" });
    });
  });
}

export function OptionsApp(): React.ReactElement {
  const [settings, setSettings] = useState<ExtensionSettings>(DEFAULT_EXTENSION_SETTINGS);
  const [status, setStatus] = useState<string>("");

  useEffect(() => {
    void sendMessage<ExtensionSettings>({ type: "PROJECT_T_GET_SETTINGS" }).then((res) => {
      if (res.ok) {
        setSettings(res.data);
      }
    });
  }, []);

  const handleSave = async (event: React.FormEvent) => {
    event.preventDefault();
    const res = await sendMessage<ExtensionSettings>({
      type: "PROJECT_T_SAVE_SETTINGS",
      payload: settings
    });
    if (res.ok) {
      setSettings(res.data);
      setStatus("Settings saved cleanly to chrome.storage.local.");
    } else {
      setStatus(`Error: ${res.error}`);
    }
  };

  return (
    <form onSubmit={(e) => void handleSave(e)}>
      <h3>Project T Local Runtime Pairing</h3>
      <p>
        Connect strictly to your local Project T runtime (127.0.0.1 / localhost). Never enter
        upstream OpenAI, Anthropic, or Google API keys here.
      </p>

      <div className="pt-field">
        <label htmlFor="pt-runtime-url">Local Runtime Base URL</label>
        <input
          id="pt-runtime-url"
          className="pt-input"
          type="text"
          value={settings.runtimeUrl}
          onChange={(e) => setSettings({ ...settings, runtimeUrl: e.target.value })}
        />
      </div>

      <div className="pt-field">
        <label htmlFor="pt-bearer-token">Local Installation Bearer Token</label>
        <input
          id="pt-bearer-token"
          className="pt-input"
          type="password"
          value={settings.bearerToken}
          onChange={(e) => setSettings({ ...settings, bearerToken: e.target.value })}
        />
      </div>

      <div className="pt-field">
        <label htmlFor="pt-mode">Default Optimization Mode</label>
        <select
          id="pt-mode"
          className="pt-input"
          value={settings.mode}
          onChange={(e) => setSettings({ ...settings, mode: e.target.value as OptimizationMode })}
        >
          <option value="safe">Safe</option>
          <option value="balanced">Balanced</option>
          <option value="aggressive">Aggressive</option>
        </select>
      </div>

      <div className="pt-field">
        <label>
          <input
            type="checkbox"
            checked={settings.preserveIdentifiers}
            onChange={(e) =>
              setSettings({ ...settings, preserveIdentifiers: e.target.checked })
            }
          />{" "}
          Preserve identifiers, file paths, versions, and explicit constraints
        </label>
      </div>

      <button type="submit" className="pt-btn pt-btn-primary">
        Save Settings
      </button>

      {status && <p>{status}</p>}
    </form>
  );
}
