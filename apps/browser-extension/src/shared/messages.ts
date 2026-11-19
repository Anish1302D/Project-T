import type { OptimizationMode, OptimizationResult } from "@project-t/contracts";

export interface ExtensionSettings {
  runtimeUrl: string;
  bearerToken: string;
  mode: OptimizationMode;
  preserveIdentifiers: boolean;
}

export const DEFAULT_EXTENSION_SETTINGS: ExtensionSettings = {
  runtimeUrl: "http://127.0.0.1:4765/api/v1",
  bearerToken: "",
  mode: "balanced",
  preserveIdentifiers: true
};

export type BackgroundRequest =
  | { type: "PROJECT_T_HEALTH" }
  | {
      type: "PROJECT_T_OPTIMIZE_TEXT";
      payload: {
        text: string;
        siteId: string;
        provider?: string;
        model?: string;
      };
    }
  | { type: "PROJECT_T_GET_SETTINGS" }
  | { type: "PROJECT_T_SAVE_SETTINGS"; payload: Partial<ExtensionSettings> };

export type BackgroundResponse<T = unknown> =
  | { ok: true; data: T }
  | { ok: false; error: string; code?: string };

export interface OptimizeTextResponseData {
  result: OptimizationResult;
}

export type ContentScriptRequest =
  | { type: "PROJECT_T_TRIGGER_OPTIMIZE" }
  | { type: "PROJECT_T_RESTORE_ORIGINAL" }
  | { type: "PROJECT_T_GET_STATUS" };
