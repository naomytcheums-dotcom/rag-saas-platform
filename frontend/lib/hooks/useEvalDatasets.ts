"use client";

import { useCallback, useEffect, useState } from "react";
import * as evalService from "@/lib/services/eval";
import type { EvalDataset } from "@/lib/services/eval";

export function useEvalDatasets(orgId: string) {
  const [datasets, setDatasets] = useState<EvalDataset[]>([]);
  const [total, setTotal] = useState(0);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  const reload = useCallback(async () => {
    setLoading(true);
    try {
      const response = await evalService.listDatasets(orgId);
      setDatasets(response.items);
      setTotal(response.total);
      setError(null);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Failed to load datasets");
    } finally {
      setLoading(false);
    }
  }, [orgId]);

  useEffect(() => {
    // eslint-disable-next-line react-hooks/set-state-in-effect -- syncing with the backend after mount/org change
    void reload();
  }, [reload]);

  const create = useCallback(async (data: { name: string; description?: string }) => {
    const created = await evalService.createDataset(orgId, data);
    await reload();
    return created;
  }, [orgId, reload]);

  const remove = useCallback(async (id: string) => {
    await evalService.deleteDataset(id);
    await reload();
  }, [reload]);

  return { datasets, total, loading, error, reload, create, remove };
}
