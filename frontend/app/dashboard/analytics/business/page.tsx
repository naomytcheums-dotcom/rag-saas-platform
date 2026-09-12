"use client";

import { useState } from "react";
import { BusinessMetrics } from "@/components/analytics/BusinessMetrics";
import { DateRangePicker } from "@/components/analytics/DateRangePicker";

export default function Page() {
  const [dateRange, setDateRange] = useState("30d");
  return (
    <div className="mx-auto max-w-5xl">
      <div className="flex items-center justify-between">
        <h1 className="text-xl font-semibold text-foreground">Business metrics</h1>
        <DateRangePicker value={dateRange} onChange={setDateRange} />
      </div>
      <div className="mt-5">
        <BusinessMetrics dateRange={dateRange} />
      </div>
    </div>
  );
}
