"use client";

import { useEffect, useState } from "react";
import * as autonomousAgentsService from "@/lib/services/autonomous-agents";
import type { AgentPlan, AgentStep } from "@/lib/services/autonomous-agents";

export function useAgentPlan(agentId: string, planId: string | null) {
  const [plan, setPlan] = useState<AgentPlan | null>(null);
  const [steps, setSteps] = useState<AgentStep[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    if (!planId) return;
    let cancelled = false;
    setLoading(true);
    Promise.all([autonomousAgentsService.getAgentPlan(agentId, planId), autonomousAgentsService.listAgentSteps(agentId, planId)])
      .then(([loadedPlan, loadedSteps]) => {
        if (cancelled) return;
        setPlan(loadedPlan);
        setSteps(loadedSteps);
        setError(null);
      })
      .catch((err) => { if (!cancelled) setError(err instanceof Error ? err.message : "Failed to load plan"); })
      .finally(() => { if (!cancelled) setLoading(false); });
    return () => { cancelled = true; };
  }, [agentId, planId]);

  return { plan, steps, loading, error };
}
