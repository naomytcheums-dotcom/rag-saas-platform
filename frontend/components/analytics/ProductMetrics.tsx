"use client";

import { useEffect, useState } from "react";
import { MetricChart } from "@/components/analytics/MetricChart";
import { MetricTable } from "@/components/analytics/MetricTable";
import * as analyticsService from "@/lib/services/analytics";

interface ProductMetricsProps {
  orgId: string;
  dateRange: string;
}

export function ProductMetrics({ orgId, dateRange }: ProductMetricsProps) {
  const [data, setData] = useState<Awaited<ReturnType<typeof analyticsService.getProductMetrics>> | null>(null);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    (async () => {
      try {
        setData(await analyticsService.getProductMetrics(orgId, dateRange));
        setError(null);
      } catch (err) {
        setError(err instanceof Error ? err.message : "Failed to load product metrics");
      }
    })();
  }, [orgId, dateRange]);

  if (error) return <p className="rounded-lg bg-danger-soft px-3 py-2 text-sm text-danger">{error}</p>;
  if (!data) return <p className="text-sm text-foreground-muted">Loading…</p>;

  const adoption = data.adoption.by_event_type;
  const engagement = data.engagement.daily_active_users;
  const usage = data.usage.by_metric;

  return (
    <div className="flex flex-col gap-4">
      <div className="rounded-xl border border-border bg-surface p-5">
        <h2 className="text-xs font-medium uppercase text-foreground-muted">Daily active users</h2>
        <div className="mt-3">
          <MetricChart type="area" data={engagement.map((row) => ({ label: row.date.slice(5), value: row.active_users }))} />
        </div>
      </div>

      <div className="rounded-xl border border-border bg-surface p-5">
        <h2 className="text-xs font-medium uppercase text-foreground-muted">Feature adoption</h2>
        <div className="mt-3">
          <MetricChart type="bar" data={adoption.map((row) => ({ label: row.event_type, value: row.event_count }))} />
        </div>
      </div>

      <div>
        <h2 className="text-xs font-medium uppercase text-foreground-muted">Usage by metric</h2>
        <div className="mt-3">
          <MetricTable columns={["Metric", "Total"]} rows={Object.entries(usage).map(([metric, total]) => [metric, total as number])} />
        </div>
      </div>
    </div>
  );
}
