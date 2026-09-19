"use client";

// Real status polling while the agent is actively planning/executing --
// no fabricated progress bar (this session's own standing "pas de
// barre de progression inutile" instruction), stops once the real
// backend status settles.

import { useCallback, useEffect, useState } from "react";
import * as autonomousAgentsService from "@/lib/services/autonomous-agents";
import type { AutonomousAgent } from "@/lib/services/autonomous-agents";

const POLL_INTERVAL_MS = 2000;
const ACTIVE_STATUSES = new Set(["planning", "executing"]);

export function useAutonomousAgent(agentId: string | null) {
  const [agent, setAgent] = useState<AutonomousAgent | null>(null);
  const [error, setError] = useState<string | null>(null);

  const reload = useCallback(async () => {
    if (!agentId) return;
    try {
      setAgent(await autonomousAgentsService.getAutonomousAgent(agentId));
      setError(null);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Failed to load agent");
    }
  }, [agentId]);

  useEffect(() => {
    // eslint-disable-next-line react-hooks/set-state-in-effect -- justified: syncing with a real external system (the backend API) after mount/param change, not a value derivable from props/state.
    void reload();
  }, [reload]);

  useEffect(() => {
    if (!agentId || !agent || !ACTIVE_STATUSES.has(agent.status)) return;
    const timer = setTimeout(() => void reload(), POLL_INTERVAL_MS);
    return () => clearTimeout(timer);
  }, [agentId, agent, reload]);

  const run = useCallback(async () => { await autonomousAgentsService.runAutonomousAgent(agentId as string); await reload(); }, [agentId, reload]);
  const pause = useCallback(async () => { await autonomousAgentsService.pauseAutonomousAgent(agentId as string); await reload(); }, [agentId, reload]);
  const resume = useCallback(async () => { await autonomousAgentsService.resumeAutonomousAgent(agentId as string); await reload(); }, [agentId, reload]);
  const stop = useCallback(async () => { await autonomousAgentsService.stopAutonomousAgent(agentId as string); await reload(); }, [agentId, reload]);

  return { agent, error, reload, run, pause, resume, stop };
}
