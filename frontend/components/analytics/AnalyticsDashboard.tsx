"use client";

import { useState } from "react";
import { BusinessMetrics } from "@/components/analytics/BusinessMetrics";
import { DashboardBuilder } from "@/components/analytics/DashboardBuilder";
import { DateRangePicker } from "@/components/analytics/DateRangePicker";
import { ExportButton } from "@/components/analytics/ExportButton";
import { ProductMetrics } from "@/components/analytics/ProductMetrics";
import { TechnicalMetrics } from "@/components/analytics/TechnicalMetrics";
import { useCurrentOrg } from "@/lib/useCurrentOrg";

const TABS = ["Overview", "Business", "Product", "Technical", "Dashboards"] as const;
type Tab = (typeof TABS)[number];
const TAB_LABELS: Record<Tab, string> = {
  Overview: "Vue d'ensemble", Business: "Métier", Product: "Produit", Technical: "Technique", Dashboards: "Tableaux de bord",
};

export function AnalyticsDashboard() {
  const { org, loading: orgLoading } = useCurrentOrg();
  const [tab, setTab] = useState<Tab>("Overview");
  const [dateRange, setDateRange] = useState("30d");

  if (orgLoading || !org) {
    return <p className="mx-auto max-w-5xl text-sm text-foreground-muted">Chargement…</p>;
  }

  return (
    <div className="mx-auto max-w-5xl">
      <div className="flex flex-wrap items-center justify-between gap-3">
        <div>
          <h1 className="text-xl font-semibold text-foreground">Analytics</h1>
          <p className="mt-1 text-sm text-foreground-muted">Métriques métier, produit et techniques pour {org.name}.</p>
        </div>
        <div className="flex items-center gap-2">
          <DateRangePicker value={dateRange} onChange={setDateRange} />
          <ExportButton orgId={org.id} dateRange={dateRange} />
        </div>
      </div>

      <div className="mt-5 flex flex-wrap gap-1 border-b border-border">
        {TABS.map((t) => (
          <button
            key={t} type="button" onClick={() => setTab(t)}
            className={`rounded-t-lg px-3 py-2 text-sm font-medium ${tab === t ? "border-b-2 border-accent text-foreground" : "text-foreground-muted"}`}
          >
            {TAB_LABELS[t]}
          </button>
        ))}
      </div>

      <div className="mt-5">
        {tab === "Overview" && (
          <div className="flex flex-col gap-6">
            <BusinessMetrics dateRange={dateRange} />
            <ProductMetrics orgId={org.id} dateRange={dateRange} />
          </div>
        )}
        {tab === "Business" && <BusinessMetrics dateRange={dateRange} />}
        {tab === "Product" && <ProductMetrics orgId={org.id} dateRange={dateRange} />}
        {tab === "Technical" && <TechnicalMetrics orgId={org.id} dateRange={dateRange} />}
        {tab === "Dashboards" && <DashboardBuilder orgId={org.id} />}
      </div>
    </div>
  );
}
