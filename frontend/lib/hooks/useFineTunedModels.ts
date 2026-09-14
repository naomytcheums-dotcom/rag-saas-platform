"use client";

import { useCallback, useEffect, useState } from "react";
import * as fineTuningService from "@/lib/services/fine-tuning";
import type { FineTunedModel } from "@/lib/services/fine-tuning";

export function useFineTunedModels(orgId: string) {
  const [models, setModels] = useState<FineTunedModel[]>([]);
  const [total, setTotal] = useState(0);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  const reload = useCallback(async () => {
    setLoading(true);
    try {
      const response = await fineTuningService.listModels(orgId);
      setModels(response.items);
      setTotal(response.total);
      setError(null);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Failed to load models");
    } finally {
      setLoading(false);
    }
  }, [orgId]);

  useEffect(() => {
    void reload();
  }, [reload]);

  const deploy = useCallback(async (id: string) => { await fineTuningService.deployModel(id); await reload(); }, [reload]);
  const undeploy = useCallback(async (id: string) => { await fineTuningService.undeployModel(id); await reload(); }, [reload]);
  const remove = useCallback(async (id: string) => { await fineTuningService.deleteModel(id); await reload(); }, [reload]);

  return { models, total, loading, error, reload, deploy, undeploy, remove };
}
