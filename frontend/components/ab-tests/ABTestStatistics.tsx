"use client";

import type { ABTestMetricResult } from "@/lib/services/ab-tests";

function fmt(value: number | null, digits = 3): string {
  return value === null ? "—" : value.toFixed(digits);
}

export function ABTestStatistics({ metric, result }: { metric: string; result: ABTestMetricResult }) {
  return (
    <div className="rounded-xl border border-border bg-surface p-5">
      <div className="flex items-center justify-between">
        <h3 className="text-sm font-medium text-foreground">{metric}</h3>
        {result.significant !== null && (
          <span className={result.significant ? "rounded-full bg-success-soft px-2 py-0.5 text-xs text-success" : "rounded-full bg-surface-muted px-2 py-0.5 text-xs text-foreground-muted"}>
            {result.significant ? "Significant" : "Not significant"}
          </span>
        )}
      </div>
      <div className="mt-3 grid grid-cols-2 gap-4 text-xs text-foreground-muted sm:grid-cols-4">
        <div><p className="text-foreground-muted">Mean A</p><p className="text-foreground">{fmt(result.variant_a.mean)} (n={result.variant_a.count})</p></div>
        <div><p className="text-foreground-muted">Mean B</p><p className="text-foreground">{fmt(result.variant_b.mean)} (n={result.variant_b.count})</p></div>
        <div><p className="text-foreground-muted">p-value</p><p className="text-foreground">{fmt(result.p_value, 4)}</p></div>
        <div><p className="text-foreground-muted">Lift</p><p className="text-foreground">{result.lift === null ? "—" : `${(result.lift * 100).toFixed(1)}%`}</p></div>
        <div><p className="text-foreground-muted">95% CI</p><p className="text-foreground">[{fmt(result.confidence_interval_lower)}, {fmt(result.confidence_interval_upper)}]</p></div>
        <div><p className="text-foreground-muted">Cohen&apos;s d</p><p className="text-foreground">{fmt(result.effect_size_cohens_d)}</p></div>
        <div><p className="text-foreground-muted">Power</p><p className="text-foreground">{fmt(result.statistical_power)}</p></div>
        <div><p className="text-foreground-muted">Min sample reached</p><p className="text-foreground">{result.min_sample_size_reached ? "Yes" : "No"}</p></div>
      </div>
    </div>
  );
}
