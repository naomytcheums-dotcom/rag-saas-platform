"use client";

import { useEffect, useState } from "react";
import { AgentPlanView } from "@/components/autonomous/AgentPlanView";
import * as autonomousAgentsService from "@/lib/services/autonomous-agents";
import type { AgentPlan } from "@/lib/services/autonomous-agents";

export function AgentTimeline({ agentId }: { agentId: string }) {
  const [plans, setPlans] = useState<AgentPlan[]>([]);
  const [selectedPlanId, setSelectedPlanId] = useState<string | null>(null);

  useEffect(() => {
    autonomousAgentsService.listAgentPlans(agentId).then((loaded) => {
      setPlans(loaded);
      if (loaded.length > 0) setSelectedPlanId(loaded[0].id);
    }).catch(() => setPlans([]));
  }, [agentId]);

  if (plans.length === 0) return <p className="text-xs text-foreground-muted">No plans yet — run this agent to generate one.</p>;

  return (
    <div className="flex flex-col gap-3">
      <div className="flex gap-2 overflow-x-auto">
        {plans.map((plan) => (
          <button
            key={plan.id} type="button" onClick={() => setSelectedPlanId(plan.id)}
            className={`whitespace-nowrap rounded-full px-3 py-1 text-xs font-medium ${selectedPlanId === plan.id ? "bg-accent text-white" : "bg-surface-muted text-foreground-muted hover:bg-accent-soft"}`}
          >
            {new Date(plan.created_at).toLocaleString()}
          </button>
        ))}
      </div>
      {selectedPlanId && <AgentPlanView agentId={agentId} planId={selectedPlanId} />}
    </div>
  );
}
