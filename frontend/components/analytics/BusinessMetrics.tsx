"use client";

import { useEffect, useState } from "react";
import { ApiError } from "@/lib/api";
import { MetricCard } from "@/components/analytics/MetricCard";
import { MetricChart } from "@/components/analytics/MetricChart";
import * as analyticsService from "@/lib/services/analytics";

interface BusinessMetricsProps {
  dateRange: string;
}

function formatCents(cents: number | undefined): string {
  if (cents === undefined) return "—";
  return (cents / 100).toLocaleString(undefined, { style: "currency", currency: "EUR" });
}

function formatPercent(rate: number | null | undefined): string {
  if (rate === null || rate === undefined) return "—";
  return `${(rate * 100).toFixed(1)}%`;
}

export function BusinessMetrics({ dateRange }: BusinessMetricsProps) {
  const [data, setData] = useState<Awaited<ReturnType<typeof analyticsService.getBusinessMetrics>> | null>(null);
  const [trend, setTrend] = useState<{ date: string; mrr_cents: number }[]>([]);
  const [notAllowed, setNotAllowed] = useState(false);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    (async () => {
      try {
        const [metrics, revenueTrend] = await Promise.all([
          analyticsService.getBusinessMetrics(dateRange),
          analyticsService.getBusinessRevenueTrend(dateRange),
        ]);
        setData(metrics);
        setTrend(revenueTrend);
        setError(null);
      } catch (err) {
        if (err instanceof ApiError && err.status === 403) {
          setNotAllowed(true);
        } else {
          setError(err instanceof Error ? err.message : "Failed to load business metrics");
        }
      }
    })();
  }, [dateRange]);

  if (notAllowed) {
    return <p className="rounded-xl border border-border bg-surface p-5 text-sm text-foreground-muted">Business metrics are only visible to platform administrators.</p>;
  }
  if (error) {
    return <p className="rounded-lg bg-danger-soft px-3 py-2 text-sm text-danger">{error}</p>;
  }
  if (!data) {
    return <p className="text-sm text-foreground-muted">Loading…</p>;
  }

  return (
    <div className="flex flex-col gap-4">
      <div className="grid grid-cols-1 gap-4 sm:grid-cols-3 lg:grid-cols-5">
        <MetricCard label="MRR" value={formatCents(data.revenue?.mrr_cents)} />
        <MetricCard label="ARR" value={formatCents(data.revenue?.arr_cents)} />
        <MetricCard label="ARPU" value={formatCents(data.revenue?.arpu_cents)} />
        <MetricCard label="Churn rate" value={formatPercent(data.churn?.churn_rate)} />
        <MetricCard label="Retention" value={formatPercent(data.retention?.retention_rate)} />
      </div>
      <div className="grid grid-cols-1 gap-4 sm:grid-cols-2">
        <MetricCard label="Customer lifetime value" value={data.ltv?.ltv_cents !== null ? formatCents(data.ltv?.ltv_cents) : "Not enough data yet"} />
        <MetricCard label="Active customers" value={data.customers?.active_customers ?? "—"} hint={`${data.customers?.total_customers ?? 0} total`} />
      </div>
      <div className="rounded-xl border border-border bg-surface p-5">
        <h2 className="text-xs font-medium uppercase text-foreground-muted">Revenue trend</h2>
        <div className="mt-3">
          <MetricChart type="area" data={trend.map((point) => ({ label: point.date.slice(5), value: point.mrr_cents / 100 }))} />
        </div>
      </div>
    </div>
  );
}
