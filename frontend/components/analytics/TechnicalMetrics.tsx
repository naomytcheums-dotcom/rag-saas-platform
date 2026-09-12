"use client";

import { useEffect, useState } from "react";
import { MetricCard } from "@/components/analytics/MetricCard";
import * as analyticsService from "@/lib/services/analytics";

interface TechnicalMetricsProps {
  orgId: string;
  dateRange: string;
}

export function TechnicalMetrics({ orgId, dateRange }: TechnicalMetricsProps) {
  const [data, setData] = useState<Awaited<ReturnType<typeof analyticsService.getTechnicalMetrics>> | null>(null);
  const [notAllowed, setNotAllowed] = useState(false);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    (async () => {
      try {
        setData(await analyticsService.getTechnicalMetrics(orgId, dateRange));
        setError(null);
      } catch (err: any) {
        if (err?.status === 403) setNotAllowed(true);
        else setError(err instanceof Error ? err.message : "Failed to load technical metrics");
      }
    })();
  }, [orgId, dateRange]);

  if (notAllowed) {
    return <p className="rounded-xl border border-border bg-surface p-5 text-sm text-foreground-muted">Technical metrics are only visible to organization admins.</p>;
  }
  if (error) return <p className="rounded-lg bg-danger-soft px-3 py-2 text-sm text-danger">{error}</p>;
  if (!data) return <p className="text-sm text-foreground-muted">Loading…</p>;

  const performance = data.performance as any;
  const llmUsage = data.llmUsage as any;
  const apiUsage = data.apiUsage as any;

  return (
    <div className="flex flex-col gap-4">
      <p className="text-xs text-foreground-muted">
        Performance/error figures are platform-wide (this deployment's Prometheus counters aren't labeled per organization) --
        LLM usage below is scoped to this organization's own Evaluation Lab runs (see docs/analytics/TECHNICAL.md).
      </p>
      <div className="grid grid-cols-1 gap-4 sm:grid-cols-2 lg:grid-cols-4">
        <MetricCard label="HTTP requests (this process)" value={performance?.http_requests_total_samples ?? "—"} />
        <MetricCard label="Request duration samples" value={performance?.request_duration_observation_count ?? "—"} />
        <MetricCard label="LLM tokens (eval runs)" value={llmUsage?.total_tokens ?? "—"} />
        <MetricCard label="LLM cost (eval runs)" value={llmUsage?.total_cost !== undefined ? `$${Number(llmUsage.total_cost).toFixed(4)}` : "—"} />
      </div>
      <div className="rounded-xl border border-border bg-surface p-5">
        <h2 className="text-xs font-medium uppercase text-foreground-muted">API usage (this organization)</h2>
        <pre className="mt-2 overflow-x-auto text-xs text-foreground-muted">{JSON.stringify(apiUsage?.by_metric ?? {}, null, 2)}</pre>
      </div>
    </div>
  );
}
