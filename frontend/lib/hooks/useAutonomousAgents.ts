"use client";

import { useCallback, useEffect, useState } from "react";
import * as autonomousAgentsService from "@/lib/services/autonomous-agents";
import type { AutonomousAgent } from "@/lib/services/autonomous-agents";

export function useAutonomousAgents(orgId: string) {
  const [agents, setAgents] = useState<AutonomousAgent[]>([]);
  const [total, setTotal] = useState(0);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  const reload = useCallback(async () => {
    setLoading(true);
    try {
      const response = await autonomousAgentsService.listAutonomousAgents(orgId);
      setAgents(response.items);
      setTotal(response.total);
      setError(null);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Failed to load autonomous agents");
    } finally {
      setLoading(false);
    }
  }, [orgId]);

  useEffect(() => {
    // eslint-disable-next-line react-hooks/set-state-in-effect -- justified: syncing with a real external system (the backend API) after mount/param change, not a value derivable from props/state.
    void reload();
  }, [reload]);

  const create = useCallback(async (data: Parameters<typeof autonomousAgentsService.createAutonomousAgent>[1]) => {
    const created = await autonomousAgentsService.createAutonomousAgent(orgId, data);
    await reload();
    return created;
  }, [orgId, reload]);

  return { agents, total, loading, error, reload, create };
}
