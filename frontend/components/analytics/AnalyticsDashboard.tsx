"use client";

import dynamic from "next/dynamic";
import { useState } from "react";
import LoadingState from "@/components/LoadingState";
import { BusinessMetrics } from "@/components/analytics/BusinessMetrics";
import { DateRangePicker } from "@/components/analytics/DateRangePicker";
import { ExportButton } from "@/components/analytics/ExportButton";
import { ProductMetrics } from "@/components/analytics/ProductMetrics";
import { useCurrentOrg } from "@/lib/useCurrentOrg";
import { useTranslation } from "@/lib/i18n";

// Both pull in recharts (~390KB) -- deferred so visiting the default
// Overview/Business/Product tabs never downloads it, only actually
// opening Technical or Dashboards does.
const TechnicalMetrics = dynamic(() => import("@/components/analytics/TechnicalMetrics").then((m) => m.TechnicalMetrics), {
  loading: () => <LoadingState fullScreen={false} />,
});
const DashboardBuilder = dynamic(() => import("@/components/analytics/DashboardBuilder").then((m) => m.DashboardBuilder), {
  loading: () => <LoadingState fullScreen={false} />,
});

const TABS = ["Overview", "Business", "Product", "Technical", "Dashboards"] as const;
type Tab = (typeof TABS)[number];
const TAB_LABEL_KEYS: Record<Tab, string> = {
  Overview: "analytics.tab_overview",
  Business: "analytics.tab_business",
  Product: "analytics.tab_product",
  Technical: "analytics.tab_technical",
  Dashboards: "analytics.tab_dashboards",
};

export function AnalyticsDashboard() {
  const { org, loading: orgLoading } = useCurrentOrg();
  const { t } = useTranslation();
  const [tab, setTab] = useState<Tab>("Overview");
  const [dateRange, setDateRange] = useState("30d");

  if (orgLoading || !org) {
    return <p className="mx-auto max-w-5xl text-sm text-foreground-muted">{t("analytics.loading")}</p>;
  }

  return (
    <div className="mx-auto max-w-5xl">
      <div className="flex flex-wrap items-center justify-between gap-3">
        <div>
          <h1 className="text-xl font-semibold text-foreground">{t("analytics.title")}</h1>
          <p className="mt-1 text-sm text-foreground-muted">{t("analytics.subtitle")} {org.name}.</p>
        </div>
        <div className="flex items-center gap-2">
          <DateRangePicker value={dateRange} onChange={setDateRange} />
          <ExportButton orgId={org.id} dateRange={dateRange} />
        </div>
      </div>

      <div className="mt-5 flex flex-wrap gap-1 border-b border-border">
        {TABS.map((tabKey) => (
          <button
            key={tabKey} type="button" onClick={() => setTab(tabKey)}
            className={`rounded-t-lg px-3 py-2 text-sm font-medium ${tab === tabKey ? "border-b-2 border-accent text-foreground" : "text-foreground-muted"}`}
          >
            {t(TAB_LABEL_KEYS[tabKey])}
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
