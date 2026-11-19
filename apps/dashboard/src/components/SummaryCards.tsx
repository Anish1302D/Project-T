import {
  type AnalyticsOverview,
  formatTokenCount,
  formatUsdCost
} from "@project-t/shared-ui";

export function SummaryCards({ overview }: { overview: AnalyticsOverview }) {
  const { totals, accuracy_breakdown: acc, cost_avoided: cost } = overview;

  return (
    <div className="grid grid-cols-1 gap-4 lg:grid-cols-3">
      {/* View 1: Original vs Optimized Tokens */}
      <article
        data-testid="view-original-vs-optimized"
        className="rounded-xl border border-slate-800 bg-slate-900/70 p-4"
      >
        <div className="flex items-center justify-between">
          <h2 className="text-sm font-semibold text-slate-200">
            1. Original vs. Optimized Tokens
          </h2>
          <span className="rounded bg-slate-800 px-2 py-0.5 font-mono text-xs text-slate-300">
            {totals.total_runs} runs
          </span>
        </div>
        <div className="mt-3 grid grid-cols-2 gap-3">
          <div className="rounded-lg bg-slate-950/70 p-3">
            <div className="text-xs text-slate-400">Original Baseline</div>
            <div data-testid="metric-original-tokens" className="mt-1 font-mono text-xl font-bold text-slate-100">
              {formatTokenCount(totals.original_tokens)}
            </div>
          </div>
          <div className="rounded-lg bg-slate-950/70 p-3">
            <div className="text-xs text-slate-400">After Optimization</div>
            <div data-testid="metric-optimized-tokens" className="mt-1 font-mono text-xl font-bold text-indigo-300">
              {formatTokenCount(totals.optimized_tokens)}
            </div>
          </div>
        </div>
        <p className="mt-2.5 text-xs text-slate-400">
          Net aggregate reduction:{" "}
          <span className="font-mono font-semibold text-emerald-300">
            {totals.reduction_percentage.toFixed(2)}%
          </span>
        </p>
      </article>

      {/* View 2: Net Tokens Saved (exact vs estimated vs provider-confirmed) */}
      <article
        data-testid="view-net-tokens-saved"
        className="rounded-xl border border-slate-800 bg-slate-900/70 p-4"
      >
        <div className="flex items-center justify-between">
          <h2 className="text-sm font-semibold text-slate-200">
            2. Net Tokens Saved by Accuracy
          </h2>
          <span data-testid="metric-net-saved" className="font-mono text-lg font-bold text-emerald-300">
            {formatTokenCount(totals.tokens_saved)}
          </span>
        </div>
        <dl className="mt-3 space-y-2 text-xs">
          <div className="flex items-center justify-between rounded bg-emerald-500/10 px-2.5 py-1.5">
            <dt className="text-emerald-200">Exact (tiktoken BPE, {acc.exact_runs} runs)</dt>
            <dd data-testid="metric-exact-saved" className="font-mono font-semibold text-emerald-300">
              {formatTokenCount(acc.exact_tokens_saved)}
            </dd>
          </div>
          <div className="flex items-center justify-between rounded bg-amber-500/10 px-2.5 py-1.5">
            <dt className="text-amber-200">Estimated ({acc.estimated_runs} runs)</dt>
            <dd data-testid="metric-estimated-saved" className="font-mono font-semibold text-amber-300">
              {formatTokenCount(acc.estimated_tokens_saved)}
            </dd>
          </div>
          <div className="flex items-center justify-between rounded bg-sky-500/10 px-2.5 py-1.5">
            <dt className="text-sky-200">Provider-Confirmed ({acc.provider_confirmed_runs} runs)</dt>
            <dd data-testid="metric-confirmed-saved" className="font-mono font-semibold text-sky-300">
              {formatTokenCount(acc.provider_confirmed_tokens_saved)} saved ({formatTokenCount(acc.provider_confirmed_input_tokens)} billed)
            </dd>
          </div>
        </dl>
      </article>

      {/* View 3: Estimated vs Confirmed Cost Avoided */}
      <article
        data-testid="view-cost-avoided"
        className="rounded-xl border border-slate-800 bg-slate-900/70 p-4"
      >
        <div className="flex items-center justify-between">
          <h2 className="text-sm font-semibold text-slate-200">
            3. Estimated Cost Avoided
          </h2>
          <span className="rounded bg-slate-800 px-2 py-0.5 font-mono text-[11px] text-slate-300">
            {cost.pricing_versions.length > 0 ? cost.pricing_versions.join(", ") : "n/a"}
          </span>
        </div>
        <div className="mt-3 grid grid-cols-2 gap-3">
          <div className="rounded-lg bg-slate-950/70 p-3">
            <div className="text-xs text-amber-300/90">Pre-flight Estimated</div>
            <div data-testid="metric-estimated-cost" className="mt-1 font-mono text-xl font-bold text-slate-100">
              {formatUsdCost(cost.estimated_cost_avoided_usd)}
            </div>
          </div>
          <div className="rounded-lg bg-slate-950/70 p-3">
            <div className="text-xs text-sky-300/90">Provider-Confirmed</div>
            <div data-testid="metric-confirmed-cost" className="mt-1 font-mono text-xl font-bold text-sky-300">
              {formatUsdCost(cost.provider_confirmed_cost_avoided_usd)}
            </div>
          </div>
        </div>
        <p className="mt-2.5 text-xs text-slate-400">
          Attributed strictly via versioned provider catalog rates; unconfirmed estimates stay separated.
        </p>
      </article>
    </div>
  );
}
