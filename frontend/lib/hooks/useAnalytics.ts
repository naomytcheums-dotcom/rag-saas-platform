"use client";

import { useCallback, useEffect, useState } from "react";
import * as analyticsService from "@/lib/services/analytics";

export function useAnalytics(orgId: string, dateRange = "30d") {
  const [business, setBusiness] = useState<Awaited<ReturnType<typeof analyticsService.getBusinessMetrics>> | null>(null);
  const [product, setProduct] = useState<Awaited<ReturnType<typeof analyticsService.getProductMetrics>> | null>(null);
  const [technical, setTechnical] = useState<Awaited<ReturnType<typeof analyticsService.getTechnicalMetrics>> | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  const reload = useCallback(async () => {
    setLoading(true);
    try {
      const [productMetrics, technicalMetrics] = await Promise.all([
        analyticsService.getProductMetrics(orgId, dateRange),
        analyticsService.getTechnicalMetrics(orgId, dateRange),
      ]);
      setProduct(productMetrics);
      setTechnical(technicalMetrics);
      setError(null);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Failed to load analytics");
    } finally {
      setLoading(false);
    }
  }, [orgId, dateRange]);

  const loadBusiness = useCallback(async () => {
    try {
      setBusiness(await analyticsService.getBusinessMetrics(dateRange));
    } catch {
      // Business metrics are superadmin-only -- a non-superadmin caller
      // simply doesn't see this section, not a hard error for the page.
    }
  }, [dateRange]);

  useEffect(() => {
    // eslint-disable-next-line react-hooks/set-state-in-effect -- justified: syncing with a real external system (the backend API) after mount/param change, not a value derivable from props/state.
    void reload();
    void loadBusiness();
  }, [reload, loadBusiness]);

  return { business, product, technical, loading, error, reload };
}
