"use client";

import { useCallback, useEffect, useState } from "react";
import * as workflowService from "@/lib/services/workflows";
import type { Workflow } from "@/lib/services/workflows";

export function useWorkflows(orgId: string) {
  const [workflows, setWorkflows] = useState<Workflow[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  const reload = useCallback(async () => {
    if (!orgId) return;
    try {
      const items = await workflowService.listWorkflows(orgId);
      setWorkflows(items);
      setError(null);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Failed to load workflows");
    } finally {
      setLoading(false);
    }
  }, [orgId]);

  useEffect(() => {
    // eslint-disable-next-line react-hooks/set-state-in-effect -- justified: syncing with a real external system (the backend API) after mount/param change, not a value derivable from props/state.
    void reload();
  }, [reload]);

  return { workflows, loading, error, reload };
}
