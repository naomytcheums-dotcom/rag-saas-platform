"use client";

import { useCallback, useEffect, useState } from "react";
import * as fineTuningService from "@/lib/services/fine-tuning";
import type { FineTuningDataset } from "@/lib/services/fine-tuning";

export function useFineTuningDatasets(orgId: string) {
  const [datasets, setDatasets] = useState<FineTuningDataset[]>([]);
  const [total, setTotal] = useState(0);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  const reload = useCallback(async () => {
    setLoading(true);
    try {
      const response = await fineTuningService.listDatasets(orgId);
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
    void reload();
  }, [reload]);

  const upload = useCallback(async (data: Parameters<typeof fineTuningService.createDataset>[1], file: File) => {
    const created = await fineTuningService.createDataset(orgId, data, file);
    await reload();
    return created;
  }, [orgId, reload]);

  const remove = useCallback(async (id: string) => {
    await fineTuningService.deleteDataset(id);
    await reload();
  }, [reload]);

  return { datasets, total, loading, error, reload, upload, remove };
}
