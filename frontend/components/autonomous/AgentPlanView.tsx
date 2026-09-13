"use client";

import { AgentStepView } from "@/components/autonomous/AgentStepView";
import { useAgentPlan } from "@/lib/hooks/useAgentPlan";

export function AgentPlanView({ agentId, planId }: { agentId: string; planId: string }) {
  const { plan, steps, loading, error } = useAgentPlan(agentId, planId);

  if (loading) return <p className="text-sm text-foreground-muted">Loading plan…</p>;
  if (error) return <p className="rounded-lg bg-danger-soft px-3 py-2 text-sm text-danger">{error}</p>;
  if (!plan) return null;

  return (
    <div className="flex flex-col gap-3">
      <div className="flex items-center justify-between">
        <p className="text-sm font-medium text-foreground">{plan.goal}</p>
        <span className="text-xs text-foreground-muted">{plan.status}</span>
      </div>
      <div className="flex flex-col gap-2">
        {steps.map((step) => <AgentStepView key={step.id} step={step} />)}
      </div>
    </div>
  );
}
