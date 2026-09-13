"use client";

import Link from "next/link";
import { AgentStatusBadge } from "@/components/autonomous/AgentStatusBadge";
import type { AutonomousAgent } from "@/lib/services/autonomous-agents";

export function AgentCard({ agent }: { agent: AutonomousAgent }) {
  return (
    <Link href={`/dashboard/autonomous-agents/${agent.id}`} className="block rounded-xl border border-border bg-surface p-4 hover:border-accent">
      <div className="flex items-center justify-between">
        <span className="text-sm font-medium text-foreground">{agent.name}</span>
        <AgentStatusBadge status={agent.status} />
      </div>
      <p className="mt-2 line-clamp-2 text-xs text-foreground-muted">{agent.goal}</p>
      <div className="mt-3 flex gap-3 text-xs text-foreground-muted">
        <span>Step {agent.current_step}/{agent.max_steps}</span>
      </div>
    </Link>
  );
}
