"use client";

import { useCallback, useEffect, useState } from "react";
import { getMetrics } from "@/lib/services/analytics";
import type { MetricPoint } from "@/lib/services/analytics";

export function useMetrics(orgId: string, metricName?: string, period = "day", dateRange = "30d") {
  const [points, setPoints] = useState<MetricPoint[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  const reload = useCallback(async () => {
    setLoading(true);
    try {
      setPoints(await getMetrics(orgId, { metric_name: metricName, period, date_range: dateRange }));
      setError(null);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Failed to load metrics");
    } finally {
      setLoading(false);
    }
  }, [orgId, metricName, period, dateRange]);

  useEffect(() => {
    // eslint-disable-next-line react-hooks/set-state-in-effect -- justified: syncing with a real external system (the backend API) after mount/param change, not a value derivable from props/state.
    void reload();
  }, [reload]);

  return { points, loading, error, reload };
}
