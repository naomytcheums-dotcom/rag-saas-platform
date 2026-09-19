"use client";

import { useCallback, useEffect, useState } from "react";
import * as dashboardService from "@/lib/services/analytics";
import type { Dashboard } from "@/lib/services/analytics";

export function useDashboards(orgId: string) {
  const [dashboards, setDashboards] = useState<Dashboard[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  const reload = useCallback(async () => {
    setLoading(true);
    try {
      setDashboards(await dashboardService.listDashboards(orgId));
      setError(null);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Failed to load dashboards");
    } finally {
      setLoading(false);
    }
  }, [orgId]);

  useEffect(() => {
    // eslint-disable-next-line react-hooks/set-state-in-effect -- justified: syncing with a real external system (the backend API) after mount/param change, not a value derivable from props/state.
    void reload();
  }, [reload]);

  const create = useCallback(async (data: { name: string; widgets?: unknown[]; is_default?: boolean }) => {
    const created = await dashboardService.createDashboard(orgId, data);
    await reload();
    return created;
  }, [orgId, reload]);

  const update = useCallback(async (dashboardId: string, data: Partial<{ name: string; widgets: unknown[]; is_default: boolean }>) => {
    const updated = await dashboardService.updateDashboard(orgId, dashboardId, data);
    await reload();
    return updated;
  }, [orgId, reload]);

  const remove = useCallback(async (dashboardId: string) => {
    await dashboardService.deleteDashboard(orgId, dashboardId);
    await reload();
  }, [orgId, reload]);

  return { dashboards, loading, error, reload, create, update, remove };
}
