import {
  formatTokenCount,
  formatUsdCost,
  type AnalyticsOverview
} from "@project-t/shared-ui";
import { HorizontalBreakdownChart, TrendSvgChart } from "../charts/SvgCharts";
import { FilterBar } from "../components/FilterBar";
import { SummaryCards } from "../components/SummaryCards";
import { useAnalytics } from "../hooks/useAnalytics";

export function DashboardPage({ initialOverview }: { initialOverview?: AnalyticsOverview }) {
  const {
    apiBaseUrl,
    filters,
    setFilters,
    resetFilters,
    overview,
    dataSource,
    loading,
    error,
    signIn,
    disconnect,
    refresh
  } = useAnalytics(initialOverview);

  const latencyItems = [
    { label: "p50 median", value: overview.latency.p50_ms, accentClass: "bg-emerald-500" },
    { label: "average", value: overview.latency.avg_ms, accentClass: "bg-sky-500" },
    { label: "p90", value: overview.latency.p90_ms, accentClass: "bg-indigo-500" },
    { label: "p95 (target < 100 ms)", value: overview.latency.p95_ms, accentClass: "bg-amber-500" },
    { label: "p99", value: overview.latency.p99_ms, accentClass: "bg-rose-500" }
  ];

  return (
    <div className="mx-auto max-w-7xl space-y-6 px-4 py-6 sm:px-6 lg:px-8">
      <header className="flex flex-wrap items-center justify-between gap-4 border-b border-slate-800 pb-4">
        <div>
          <h1 className="text-2xl font-bold tracking-tight text-slate-50">
            Project T Cloud Control Plane & Analytics
          </h1>
          <p className="mt-1 text-xs text-slate-400">
            Model-independent token savings, versioned cost attribution, quality benchmarks, and multi-device telemetry
          </p>
        </div>
        <div className="rounded-lg border border-slate-800 bg-slate-900 px-3 py-1.5 text-xs text-slate-300">
          Paired Devices:{" "}
          <span data-testid="device-count" className="font-mono font-semibold text-indigo-300">
            {overview.devices.length}
          </span>
        </div>
      </header>

      <FilterBar
        apiBaseUrl={apiBaseUrl}
        dataSource={dataSource}
        loading={loading}
        error={error}
        filters={filters}
        devices={overview.devices}
        onChangeFilters={setFilters}
        onResetFilters={resetFilters}
        onSignIn={signIn}
        onDisconnect={disconnect}
        onRefresh={refresh}
      />

      {/* Views 1, 2, 3 */}
      <SummaryCards overview={overview} />

      {/* Views 4 & 5: Provider/Model & Integration Breakdown */}
      <div className="grid grid-cols-1 gap-4 lg:grid-cols-2">
        <article
          data-testid="view-provider-model"
          className="rounded-xl border border-slate-800 bg-slate-900/70 p-4"
        >
          <h2 className="text-sm font-semibold text-slate-200">
            4. Provider & Model Breakdown
          </h2>
          <div className="mt-3 overflow-x-auto">
            <table className="w-full text-left text-xs">
              <thead>
                <tr className="border-b border-slate-800 text-slate-400">
                  <th className="py-2 pr-2">Provider / Model</th>
                  <th className="py-2 pr-2 text-right">Runs</th>
                  <th className="py-2 pr-2 text-right">Saved</th>
                  <th className="py-2 pr-2 text-right">Red. %</th>
                  <th className="py-2 text-right">Est. Cost</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-slate-800/70">
                {overview.by_provider_model.map((row) => (
                  <tr key={`${row.provider}:${row.model}`}>
                    <td className="py-2 pr-2 font-medium text-slate-200">
                      {row.provider} / <span className="font-mono text-indigo-300">{row.model}</span>
                    </td>
                    <td className="py-2 pr-2 text-right font-mono text-slate-300">{row.runs}</td>
                    <td className="py-2 pr-2 text-right font-mono text-emerald-300">
                      {formatTokenCount(row.tokens_saved)}
                    </td>
                    <td className="py-2 pr-2 text-right font-mono text-slate-300">
                      {row.reduction_percentage.toFixed(2)}%
                    </td>
                    <td className="py-2 text-right font-mono text-slate-200">
                      {formatUsdCost(row.estimated_cost_avoided_usd)}
                    </td>
                  </tr>
                ))}
                {overview.by_provider_model.length === 0 && (
                  <tr>
                    <td colSpan={5} className="py-4 text-center text-slate-400">
                      No provider/model data matches current filters.
                    </td>
                  </tr>
                )}
              </tbody>
            </table>
          </div>
        </article>

        <article
          data-testid="view-integration-breakdown"
          className="rounded-xl border border-slate-800 bg-slate-900/70 p-4"
        >
          <h2 className="mb-3 text-sm font-semibold text-slate-200">
            5. Integration Breakdown (VS Code, Browser, MCP, Gateway)
          </h2>
          <HorizontalBreakdownChart
            items={overview.by_integration.map((item) => ({
              label: item.integration,
              value: item.tokens_saved,
              sublabel: `${item.runs} runs · ${item.reduction_percentage.toFixed(1)}%`,
              accentClass: "bg-sky-500"
            }))}
            unitSuffix=" tok"
          />
        </article>
      </div>

      {/* View 6: Daily / Weekly / Monthly Trends */}
      <article
        data-testid="view-usage-trends"
        className="rounded-xl border border-slate-800 bg-slate-900/70 p-4"
      >
        <div className="mb-3 flex flex-wrap items-center justify-between gap-2">
          <h2 className="text-sm font-semibold text-slate-200">
            6. Token Usage Trend ({overview.granularity})
          </h2>
          <div className="flex items-center gap-4 text-[11px] text-slate-400">
            <span className="flex items-center gap-1.5">
              <span className="inline-block h-2.5 w-2.5 rounded-sm bg-slate-600" /> Original
            </span>
            <span className="flex items-center gap-1.5">
              <span className="inline-block h-2.5 w-2.5 rounded-sm bg-indigo-500" /> Optimized
            </span>
            <span className="flex items-center gap-1.5">
              <span className="inline-block h-2.5 w-2.5 rounded-sm bg-emerald-400" /> Exact Saved
            </span>
          </div>
        </div>
        <TrendSvgChart buckets={overview.trends} />
      </article>

      {/* Views 7 & 8: Modes/Methods & Validation/Fallback Rates */}
      <div className="grid grid-cols-1 gap-4 lg:grid-cols-2">
        <article
          data-testid="view-modes-methods"
          className="rounded-xl border border-slate-800 bg-slate-900/70 p-4"
        >
          <h2 className="mb-3 text-sm font-semibold text-slate-200">
            7. Optimization Modes & Methods Distribution
          </h2>
          <div className="grid grid-cols-1 gap-4 sm:grid-cols-2">
            <div>
              <h3 className="mb-2 text-xs font-medium uppercase tracking-wider text-slate-400">
                Modes
              </h3>
              <HorizontalBreakdownChart
                items={overview.modes_and_methods.by_mode.map((m) => ({
                  label: m.mode,
                  value: m.runs,
                  sublabel: `${formatTokenCount(m.tokens_saved)} tok saved`,
                  accentClass: "bg-indigo-500"
                }))}
                unitSuffix=" runs"
              />
            </div>
            <div>
              <h3 className="mb-2 text-xs font-medium uppercase tracking-wider text-slate-400">
                Methods Applied
              </h3>
              <HorizontalBreakdownChart
                items={overview.modes_and_methods.by_method.map((m) => ({
                  label: m.method,
                  value: m.count,
                  accentClass: "bg-emerald-500"
                }))}
                unitSuffix="x"
              />
            </div>
          </div>
        </article>

        <article
          data-testid="view-validation-fallbacks"
          className="rounded-xl border border-slate-800 bg-slate-900/70 p-4"
        >
          <div className="flex items-center justify-between">
            <h2 className="text-sm font-semibold text-slate-200">
              8. Validation Failures & Fallback Rates
            </h2>
            <span className="font-mono text-xs text-slate-300">
              Fallback rate: {overview.validation.fallback_rate_pct.toFixed(2)}%
            </span>
          </div>
          <dl className="mt-3 grid grid-cols-2 gap-3 text-xs">
            <div className="rounded-lg bg-slate-950/70 p-3">
              <dt className="text-slate-400">Validated Runs</dt>
              <dd className="mt-1 font-mono text-lg font-bold text-emerald-300">
                {overview.validation.validated_runs}
              </dd>
            </div>
            <div className="rounded-lg bg-slate-950/70 p-3">
              <dt className="text-slate-400">Validation Failure Fallbacks</dt>
              <dd className="mt-1 font-mono text-lg font-bold text-rose-300">
                {overview.validation.fallback_validation_failed} ({overview.validation.validation_failure_rate_pct.toFixed(2)}%)
              </dd>
            </div>
            <div className="rounded-lg bg-slate-950/70 p-3">
              <dt className="text-slate-400">No-Savings Guard Fallbacks</dt>
              <dd className="mt-1 font-mono text-lg font-bold text-amber-300">
                {overview.validation.fallback_no_savings}
              </dd>
            </div>
            <div className="rounded-lg bg-slate-950/70 p-3">
              <dt className="text-slate-400">Error Fail-Open Fallbacks</dt>
              <dd className="mt-1 font-mono text-lg font-bold text-slate-200">
                {overview.validation.fallback_error}
              </dd>
            </div>
          </dl>
        </article>
      </div>

      {/* Views 9 & 10: Quality Benchmarks & Latency Percentiles */}
      <div className="grid grid-cols-1 gap-4 lg:grid-cols-3">
        <article
          data-testid="view-benchmark-summaries"
          className="rounded-xl border border-slate-800 bg-slate-900/70 p-4 lg:col-span-2"
        >
          <h2 className="text-sm font-semibold text-slate-200">
            9. Quality Benchmark Summaries
          </h2>
          <div className="mt-3 overflow-x-auto">
            <table className="w-full text-left text-xs">
              <thead>
                <tr className="border-b border-slate-800 text-slate-400">
                  <th className="py-2 pr-2">Category</th>
                  <th className="py-2 pr-2">Model</th>
                  <th className="py-2 pr-2 text-right">Samples</th>
                  <th className="py-2 pr-2 text-right">Constraints</th>
                  <th className="py-2 pr-2 text-right">Identifiers</th>
                  <th className="py-2 pr-2 text-right">Med. Red. %</th>
                  <th className="py-2 text-right">p95 ms</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-slate-800/70">
                {overview.benchmarks.map((b) => (
                  <tr key={b.id}>
                    <td className="py-2 pr-2 font-medium capitalize text-slate-200">
                      {b.category}
                    </td>
                    <td className="py-2 pr-2 font-mono text-slate-300">{b.model_name}</td>
                    <td className="py-2 pr-2 text-right font-mono text-slate-300">{b.sample_count}</td>
                    <td className="py-2 pr-2 text-right font-mono text-emerald-300">
                      {b.constraint_preservation_rate !== null
                        ? `${(b.constraint_preservation_rate * 100).toFixed(1)}%`
                        : "n/a"}
                    </td>
                    <td className="py-2 pr-2 text-right font-mono text-emerald-300">
                      {b.identifier_preservation_rate !== null
                        ? `${(b.identifier_preservation_rate * 100).toFixed(1)}%`
                        : "n/a"}
                    </td>
                    <td className="py-2 pr-2 text-right font-mono text-indigo-300">
                      {b.median_reduction_pct !== null
                        ? `${b.median_reduction_pct.toFixed(2)}%`
                        : "n/a"}
                    </td>
                    <td className="py-2 text-right font-mono text-slate-300">
                      {b.p95_latency_ms !== null ? b.p95_latency_ms.toFixed(2) : "n/a"}
                    </td>
                  </tr>
                ))}
                {overview.benchmarks.length === 0 && (
                  <tr>
                    <td colSpan={7} className="py-4 text-center text-slate-400">
                      No benchmark summaries synced yet.
                    </td>
                  </tr>
                )}
              </tbody>
            </table>
          </div>
        </article>

        <article
          data-testid="view-latency-percentiles"
          className="rounded-xl border border-slate-800 bg-slate-900/70 p-4"
        >
          <div className="mb-3 flex items-center justify-between">
            <h2 className="text-sm font-semibold text-slate-200">
              10. Optimization Latency Percentiles
            </h2>
            <span className="font-mono text-xs text-slate-400">
              {overview.latency.sample_count} samples
            </span>
          </div>
          <HorizontalBreakdownChart items={latencyItems} unitSuffix=" ms" />
        </article>
      </div>
    </div>
  );
}
