"use client";

import { useCallback, useEffect, useState } from "react";
import * as abTestService from "@/lib/services/ab-tests";
import type { ABTestResultsResponse } from "@/lib/services/ab-tests";

export function useABTestResults(id: string) {
  const [results, setResults] = useState<ABTestResultsResponse | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  const reload = useCallback(async () => {
    setLoading(true);
    try {
      setResults(await abTestService.getABTestResults(id));
      setError(null);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Failed to load results");
    } finally {
      setLoading(false);
    }
  }, [id]);

  useEffect(() => {
    // eslint-disable-next-line react-hooks/set-state-in-effect -- justified: syncing with a real external system (the backend API) after mount/param change, not a value derivable from props/state.
    void reload();
  }, [reload]);

  return { results, loading, error, reload };
}
