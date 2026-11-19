import { useState } from "react";
import type { AnalyticsFilters, AnalyticsGranularity, PairedDeviceSummary } from "@project-t/shared-ui";

interface FilterBarProps {
  apiBaseUrl: string;
  dataSource: "live" | "offline-demo";
  loading: boolean;
  error: string | null;
  filters: AnalyticsFilters;
  devices: PairedDeviceSummary[];
  onChangeFilters: (next: AnalyticsFilters) => void;
  onResetFilters: () => void;
  onSignIn: (baseUrl: string, email: string, password: string) => Promise<void>;
  onDisconnect: () => void;
  onRefresh: () => void;
}

export function FilterBar({
  apiBaseUrl,
  dataSource,
  loading,
  error,
  filters,
  devices,
  onChangeFilters,
  onResetFilters,
  onSignIn,
  onDisconnect,
  onRefresh
}: FilterBarProps) {
  const [urlInput, setUrlInput] = useState(apiBaseUrl || "http://127.0.0.1:4780");
  const [emailInput, setEmailInput] = useState("");
  const [passwordInput, setPasswordInput] = useState("");

  return (
    <section className="space-y-3 rounded-xl border border-slate-800 bg-slate-900/70 p-4">
      <div className="flex flex-wrap items-center justify-between gap-3">
        <div className="flex items-center gap-2">
          <span
            data-testid="data-source-badge"
            className={`rounded-full px-2.5 py-0.5 text-xs font-medium ${
              dataSource === "live"
                ? "bg-emerald-500/20 text-emerald-300 ring-1 ring-emerald-500/40"
                : "bg-amber-500/20 text-amber-300 ring-1 ring-amber-500/40"
            }`}
          >
            {dataSource === "live" ? "Live Control Plane" : "Offline Preview Fixture"}
          </span>
          <span className="text-xs text-slate-400">
            Metadata-only analytics — raw prompts & source code are never synced by default
          </span>
        </div>

        <div className="flex flex-wrap items-center gap-2">
          {dataSource === "live" ? (
            <>
              <button
                type="button"
                onClick={onRefresh}
                disabled={loading}
                className="rounded-lg border border-slate-700 bg-slate-800 px-3 py-1.5 text-xs font-medium text-slate-200 hover:bg-slate-700"
              >
                {loading ? "Refreshing..." : "Refresh"}
              </button>
              <button
                type="button"
                onClick={onDisconnect}
                className="rounded-lg border border-slate-700 px-3 py-1.5 text-xs text-slate-300 hover:bg-slate-800"
              >
                Switch to Offline Preview
              </button>
            </>
          ) : (
            <form
              className="flex flex-wrap items-center gap-2"
              onSubmit={(e) => {
                e.preventDefault();
                void onSignIn(urlInput, emailInput, passwordInput);
              }}
            >
              <input
                type="text"
                aria-label="Control Plane URL"
                placeholder="Control Plane URL"
                value={urlInput}
                onChange={(e) => setUrlInput(e.target.value)}
                className="w-44 rounded-lg border border-slate-700 bg-slate-950 px-2.5 py-1 text-xs text-slate-200"
              />
              <input
                type="email"
                aria-label="Cloud email"
                placeholder="Email"
                value={emailInput}
                onChange={(e) => setEmailInput(e.target.value)}
                className="w-40 rounded-lg border border-slate-700 bg-slate-950 px-2.5 py-1 text-xs text-slate-200"
              />
              <input
                type="password"
                aria-label="Cloud password"
                placeholder="Password"
                value={passwordInput}
                onChange={(e) => setPasswordInput(e.target.value)}
                className="w-32 rounded-lg border border-slate-700 bg-slate-950 px-2.5 py-1 text-xs text-slate-200"
              />
              <button
                type="submit"
                disabled={loading}
                className="rounded-lg bg-indigo-600 px-3 py-1 text-xs font-medium text-white hover:bg-indigo-500"
              >
                {loading ? "Connecting..." : "Connect"}
              </button>
            </form>
          )}
        </div>
      </div>

      {error && (
        <div role="alert" className="rounded-lg border border-rose-500/40 bg-rose-500/10 px-3 py-2 text-xs text-rose-300">
          {error}
        </div>
      )}

      <div className="grid grid-cols-2 gap-2.5 sm:grid-cols-3 lg:grid-cols-7">
        <label className="space-y-1 text-xs text-slate-400">
          <span>Granularity</span>
          <select
            aria-label="Granularity"
            data-testid="filter-granularity"
            value={filters.granularity}
            onChange={(e) =>
              onChangeFilters({
                ...filters,
                granularity: e.target.value as AnalyticsGranularity
              })
            }
            className="w-full rounded-lg border border-slate-700 bg-slate-950 px-2.5 py-1.5 text-xs text-slate-100"
          >
            <option value="daily">Daily</option>
            <option value="weekly">Weekly</option>
            <option value="monthly">Monthly</option>
          </select>
        </label>

        <label className="space-y-1 text-xs text-slate-400">
          <span>Provider</span>
          <select
            aria-label="Provider"
            data-testid="filter-provider"
            value={filters.provider ?? ""}
            onChange={(e) => onChangeFilters({ ...filters, provider: e.target.value })}
            className="w-full rounded-lg border border-slate-700 bg-slate-950 px-2.5 py-1.5 text-xs text-slate-100"
          >
            <option value="">All providers</option>
            <option value="openai">OpenAI</option>
            <option value="anthropic">Anthropic</option>
            <option value="google">Google</option>
            <option value="local">Local</option>
          </select>
        </label>

        <label className="space-y-1 text-xs text-slate-400">
          <span>Integration</span>
          <select
            aria-label="Integration"
            data-testid="filter-integration"
            value={filters.integration ?? ""}
            onChange={(e) =>
              onChangeFilters({
                ...filters,
                integration: e.target.value as AnalyticsFilters["integration"]
              })
            }
            className="w-full rounded-lg border border-slate-700 bg-slate-950 px-2.5 py-1.5 text-xs text-slate-100"
          >
            <option value="">All integrations</option>
            <option value="vscode">VS Code</option>
            <option value="browser">Browser Extension</option>
            <option value="mcp">MCP Server</option>
            <option value="gateway">API Gateway</option>
            <option value="cli">CLI</option>
            <option value="api">Local API</option>
          </select>
        </label>

        <label className="space-y-1 text-xs text-slate-400">
          <span>Mode</span>
          <select
            aria-label="Mode"
            data-testid="filter-mode"
            value={filters.mode ?? ""}
            onChange={(e) =>
              onChangeFilters({
                ...filters,
                mode: e.target.value as AnalyticsFilters["mode"]
              })
            }
            className="w-full rounded-lg border border-slate-700 bg-slate-950 px-2.5 py-1.5 text-xs text-slate-100"
          >
            <option value="">All modes</option>
            <option value="safe">Safe</option>
            <option value="balanced">Balanced</option>
            <option value="aggressive">Aggressive</option>
          </select>
        </label>

        <label className="space-y-1 text-xs text-slate-400">
          <span>Accuracy</span>
          <select
            aria-label="Accuracy"
            data-testid="filter-accuracy"
            value={filters.accuracy ?? ""}
            onChange={(e) =>
              onChangeFilters({
                ...filters,
                accuracy: e.target.value as AnalyticsFilters["accuracy"]
              })
            }
            className="w-full rounded-lg border border-slate-700 bg-slate-950 px-2.5 py-1.5 text-xs text-slate-100"
          >
            <option value="">All measurements</option>
            <option value="exact">Exact only</option>
            <option value="estimated">Estimated only</option>
          </select>
        </label>

        <label className="space-y-1 text-xs text-slate-400">
          <span>Device</span>
          <select
            aria-label="Device"
            data-testid="filter-device"
            value={filters.device_id ?? ""}
            onChange={(e) => onChangeFilters({ ...filters, device_id: e.target.value })}
            className="w-full rounded-lg border border-slate-700 bg-slate-950 px-2.5 py-1.5 text-xs text-slate-100"
          >
            <option value="">All devices</option>
            {devices.map((d) => (
              <option key={d.device_id} value={d.device_id}>
                {d.device_label}
              </option>
            ))}
          </select>
        </label>

        <div className="flex items-end">
          <button
            type="button"
            data-testid="filter-reset"
            onClick={onResetFilters}
            className="w-full rounded-lg border border-slate-700 bg-slate-800 px-3 py-1.5 text-xs font-medium text-slate-200 hover:bg-slate-700"
          >
            Reset Filters
          </button>
        </div>
      </div>
    </section>
  );
}
