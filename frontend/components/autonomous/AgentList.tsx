"use client";

import { AgentCard } from "@/components/autonomous/AgentCard";
import { useAutonomousAgents } from "@/lib/hooks/useAutonomousAgents";

export function AgentList({ orgId }: { orgId: string }) {
  const { agents, loading, error } = useAutonomousAgents(orgId);

  if (loading) return <p className="text-sm text-foreground-muted">Loading…</p>;
  if (error) return <p className="rounded-lg bg-danger-soft px-3 py-2 text-sm text-danger">{error}</p>;
  if (agents.length === 0) return <p className="rounded-xl border border-border bg-surface p-5 text-sm text-foreground-muted">No autonomous agents yet.</p>;

  return (
    <div className="grid grid-cols-1 gap-3 sm:grid-cols-2">
      {agents.map((agent) => <AgentCard key={agent.id} agent={agent} />)}
    </div>
  );
}
