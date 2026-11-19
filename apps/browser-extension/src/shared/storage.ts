import {
  DEFAULT_EXTENSION_SETTINGS,
  type ExtensionSettings
} from "./messages.js";

const SETTINGS_STORAGE_KEY = "projectTExtensionSettings";

export interface StorageAreaAdapter {
  get(keys: string | string[]): Promise<Record<string, unknown>>;
  set(items: Record<string, unknown>): Promise<void>;
}

function defaultChromeStorage(): StorageAreaAdapter {
  return {
    get: (keys) => chrome.storage.local.get(keys),
    set: (items) => chrome.storage.local.set(items)
  };
}

export async function loadExtensionSettings(
  storage: StorageAreaAdapter = defaultChromeStorage()
): Promise<ExtensionSettings> {
  const data = await storage.get(SETTINGS_STORAGE_KEY);
  const raw = (data[SETTINGS_STORAGE_KEY] ?? {}) as Partial<ExtensionSettings>;
  return {
    runtimeUrl:
      typeof raw.runtimeUrl === "string" && raw.runtimeUrl.trim()
        ? raw.runtimeUrl.trim()
        : DEFAULT_EXTENSION_SETTINGS.runtimeUrl,
    bearerToken: typeof raw.bearerToken === "string" ? raw.bearerToken.trim() : "",
    mode:
      raw.mode === "safe" || raw.mode === "balanced" || raw.mode === "aggressive"
        ? raw.mode
        : DEFAULT_EXTENSION_SETTINGS.mode,
    preserveIdentifiers:
      typeof raw.preserveIdentifiers === "boolean"
        ? raw.preserveIdentifiers
        : DEFAULT_EXTENSION_SETTINGS.preserveIdentifiers
  };
}

export async function saveExtensionSettings(
  patch: Partial<ExtensionSettings>,
  storage: StorageAreaAdapter = defaultChromeStorage()
): Promise<ExtensionSettings> {
  const current = await loadExtensionSettings(storage);
  const next: ExtensionSettings = {
    ...current,
    ...patch,
    runtimeUrl: (patch.runtimeUrl ?? current.runtimeUrl).trim(),
    bearerToken: (patch.bearerToken ?? current.bearerToken).trim()
  };
  await storage.set({ [SETTINGS_STORAGE_KEY]: next });
  return next;
}
