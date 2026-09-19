"use client";

import { useCallback, useEffect, useState } from "react";
import * as abTestService from "@/lib/services/ab-tests";
import type { ABTest } from "@/lib/services/ab-tests";

export function useABTests(orgId: string) {
  const [tests, setTests] = useState<ABTest[]>([]);
  const [total, setTotal] = useState(0);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  const reload = useCallback(async () => {
    setLoading(true);
    try {
      const response = await abTestService.listABTests(orgId);
      setTests(response.items);
      setTotal(response.total);
      setError(null);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Failed to load A/B tests");
    } finally {
      setLoading(false);
    }
  }, [orgId]);

  useEffect(() => {
    // eslint-disable-next-line react-hooks/set-state-in-effect -- justified: syncing with a real external system (the backend API) after mount/param change, not a value derivable from props/state.
    void reload();
  }, [reload]);

  const create = useCallback(async (data: Parameters<typeof abTestService.createABTest>[1]) => {
    const created = await abTestService.createABTest(orgId, data);
    await reload();
    return created;
  }, [orgId, reload]);

  return { tests, total, loading, error, reload, create };
}
