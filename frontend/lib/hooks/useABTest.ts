"use client";

import { useCallback, useEffect, useState } from "react";
import * as abTestService from "@/lib/services/ab-tests";
import type { ABTest } from "@/lib/services/ab-tests";

export function useABTest(id: string) {
  const [test, setTest] = useState<ABTest | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  const reload = useCallback(async () => {
    setLoading(true);
    try {
      setTest(await abTestService.getABTest(id));
      setError(null);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Failed to load the A/B test");
    } finally {
      setLoading(false);
    }
  }, [id]);

  useEffect(() => {
    // eslint-disable-next-line react-hooks/set-state-in-effect -- justified: syncing with a real external system (the backend API) after mount/param change, not a value derivable from props/state.
    void reload();
  }, [reload]);

  const update = useCallback(async (data: Parameters<typeof abTestService.updateABTest>[1]) => {
    const updated = await abTestService.updateABTest(id, data);
    setTest(updated);
    return updated;
  }, [id]);

  const start = useCallback(async () => setTest(await abTestService.startABTest(id)), [id]);
  const pause = useCallback(async () => setTest(await abTestService.pauseABTest(id)), [id]);
  const resume = useCallback(async () => setTest(await abTestService.resumeABTest(id)), [id]);
  const complete = useCallback(async () => setTest(await abTestService.completeABTest(id)), [id]);
  const chooseWinner = useCallback(async (variant: "a" | "b") => setTest(await abTestService.chooseABTestWinner(id, variant)), [id]);
  const decide = useCallback(async () => setTest(await abTestService.decideABTest(id)), [id]);
  const remove = useCallback(async () => abTestService.deleteABTest(id), [id]);

  return { test, loading, error, reload, update, start, pause, resume, complete, chooseWinner, decide, remove };
}
