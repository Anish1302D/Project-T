import type { TrendBucket } from "@project-t/shared-ui";

interface BarDatum {
  label: string;
  value: number;
  sublabel?: string;
  accentClass?: string;
}

export function TrendSvgChart({ buckets }: { buckets: TrendBucket[] }) {
  if (buckets.length === 0) {
    return (
      <div className="flex h-44 items-center justify-center rounded-lg border border-slate-800 bg-slate-900/40 text-sm text-slate-400">
        No trend data for selected filters.
      </div>
    );
  }

  const maxOrig = Math.max(...buckets.map((b) => b.original_tokens), 1);
  const width = Math.max(480, buckets.length * 88);
  const height = 180;
  const plotHeight = 128;

  return (
    <div className="overflow-x-auto">
      <svg
        viewBox={`0 0 ${width} ${height}`}
        className="h-48 w-full"
        role="img"
        aria-label="Token optimization trend across time buckets"
      >
        {buckets.map((bucket, index) => {
          const xBase = 24 + index * 84;
          const origH = Math.max(4, Math.round((bucket.original_tokens / maxOrig) * plotHeight));
          const optH = Math.max(4, Math.round((bucket.optimized_tokens / maxOrig) * plotHeight));
          const savedRatio =
            bucket.tokens_saved > 0 ? bucket.exact_saved / bucket.tokens_saved : 0;
          const savedBarH = Math.max(2, origH - optH);
          const exactH = Math.round(savedBarH * savedRatio);

          return (
            <g key={bucket.bucket}>
              <rect
                x={xBase}
                y={plotHeight - origH + 12}
                width={22}
                height={origH}
                rx={3}
                className="fill-slate-600"
              >
                <title>{`${bucket.bucket} original: ${bucket.original_tokens}`}</title>
              </rect>
              <rect
                x={xBase + 26}
                y={plotHeight - optH + 12}
                width={22}
                height={optH}
                rx={3}
                className="fill-indigo-500"
              >
                <title>{`${bucket.bucket} optimized: ${bucket.optimized_tokens}`}</title>
              </rect>
              {exactH > 0 && (
                <rect
                  x={xBase + 50}
                  y={plotHeight - exactH + 12}
                  width={8}
                  height={exactH}
                  rx={2}
                  className="fill-emerald-400"
                >
                  <title>{`Exact saved: ${bucket.exact_saved}`}</title>
                </rect>
              )}
              <text
                x={xBase + 24}
                y={height - 14}
                textAnchor="middle"
                className="fill-slate-400 text-[10px]"
              >
                {bucket.bucket}
              </text>
            </g>
          );
        })}
      </svg>
    </div>
  );
}

export function HorizontalBreakdownChart({
  items,
  unitSuffix = ""
}: {
  items: BarDatum[];
  unitSuffix?: string;
}) {
  if (items.length === 0) {
    return <p className="text-sm text-slate-400">No entries matching current filters.</p>;
  }
  const maxVal = Math.max(...items.map((item) => item.value), 1);

  return (
    <div className="space-y-2.5">
      {items.map((item) => {
        const pct = Math.min(100, Math.max(3, Math.round((item.value / maxVal) * 100)));
        return (
          <div key={item.label} className="space-y-1">
            <div className="flex items-center justify-between text-xs">
              <span className="font-medium text-slate-200">{item.label}</span>
              <span className="font-mono text-slate-300">
                {item.value.toLocaleString()}
                {unitSuffix}
                {item.sublabel ? ` (${item.sublabel})` : ""}
              </span>
            </div>
            <div className="h-2 w-full overflow-hidden rounded-full bg-slate-800">
              <div
                className={`h-full rounded-full ${item.accentClass ?? "bg-indigo-500"}`}
                style={{ width: `${pct}%` }}
              />
            </div>
          </div>
        );
      })}
    </div>
  );
}
