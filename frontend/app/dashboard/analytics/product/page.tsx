"use client";

import { useState } from "react";
import { DateRangePicker } from "@/components/analytics/DateRangePicker";
import { ProductMetrics } from "@/components/analytics/ProductMetrics";
import { useCurrentOrg } from "@/lib/useCurrentOrg";

export default function Page() {
  const { org, loading } = useCurrentOrg();
  const [dateRange, setDateRange] = useState("30d");

  if (loading || !org) return <p className="mx-auto max-w-5xl text-sm text-foreground-muted">Loading…</p>;

  return (
    <div className="mx-auto max-w-5xl">
      <div className="flex items-center justify-between">
        <h1 className="text-xl font-semibold text-foreground">Product metrics</h1>
        <DateRangePicker value={dateRange} onChange={setDateRange} />
      </div>
      <div className="mt-5">
        <ProductMetrics orgId={org.id} dateRange={dateRange} />
      </div>
    </div>
  );
}
