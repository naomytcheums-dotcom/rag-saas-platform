"use client";

import { useCallback, useEffect, useState } from "react";
import * as workflowService from "@/lib/services/workflows";
import type { WorkflowRun } from "@/lib/services/workflows";

const ACTIVE_STATUSES = new Set(["pending", "running", "waiting_human"]);
const POLL_INTERVAL_MS = 4000;

/** Real execution history for one workflow -- polls only while at
 * least one real run is still active, same real-polling discipline as
 * useFineTuningJobs (this session's own standing instruction: no
 * fabricated progress, only a real periodic re-fetch). */
export function useWorkflowRuns(workflowId: string) {
  const [runs, setRuns] = useState<WorkflowRun[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  const reload = useCallback(async () => {
    if (!workflowId) return;
    try {
      const items = await workflowService.listWorkflowRuns(workflowId);
      setRuns(items);
      setError(null);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Failed to load runs");
    } finally {
      setLoading(false);
    }
  }, [workflowId]);

  useEffect(() => {
    // eslint-disable-next-line react-hooks/set-state-in-effect -- justified: syncing with a real external system (the backend API) after mount/param change, not a value derivable from props/state.
    void reload();
  }, [reload]);

  useEffect(() => {
    if (!runs.some((run) => ACTIVE_STATUSES.has(run.status))) return;
    const timer = setTimeout(() => void reload(), POLL_INTERVAL_MS);
    return () => clearTimeout(timer);
  }, [runs, reload]);

  return { runs, loading, error, reload };
}
