"use client";

import { useState } from "react";
import { AgentCollaborationView } from "@/components/autonomous/AgentCollaborationView";
import { AgentGuardrailsConfig } from "@/components/autonomous/AgentGuardrailsConfig";
import { AgentMemoryView } from "@/components/autonomous/AgentMemoryView";
import { AgentRunPanel } from "@/components/autonomous/AgentRunPanel";
import { AgentStatusBadge } from "@/components/autonomous/AgentStatusBadge";
import { AgentTimeline } from "@/components/autonomous/AgentTimeline";
import { useAutonomousAgent } from "@/lib/hooks/useAutonomousAgent";

const TABS = ["Plan", "Memory", "Collaboration", "Guardrails"] as const;

export function AgentDetail({ agentId }: { agentId: string }) {
  const { agent, error, reload, run, pause, resume, stop } = useAutonomousAgent(agentId);
  const [tab, setTab] = useState<(typeof TABS)[number]>("Plan");

  if (error) return <p className="rounded-lg bg-danger-soft px-3 py-2 text-sm text-danger">{error}</p>;
  if (!agent) return <p className="text-sm text-foreground-muted">Loading…</p>;

  return (
    <div className="flex flex-col gap-5">
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-lg font-semibold text-foreground">{agent.name}</h1>
          <p className="text-sm text-foreground-muted">{agent.goal}</p>
        </div>
        <AgentStatusBadge status={agent.status} />
      </div>

      {agent.status === "error" && agent.error && <p className="rounded-lg bg-danger-soft px-3 py-2 text-sm text-danger">{agent.error}</p>}

      <AgentRunPanel agent={agent} onRun={run} onPause={pause} onResume={resume} onStop={stop} />

      <p className="text-xs text-foreground-muted">Step {agent.current_step} of {agent.max_steps}</p>

      <div className="flex gap-2 border-b border-border">
        {TABS.map((t) => (
          <button
            key={t} type="button" onClick={() => setTab(t)}
            className={`border-b-2 px-3 py-2 text-sm font-medium ${tab === t ? "border-accent text-accent" : "border-transparent text-foreground-muted"}`}
          >
            {t}
          </button>
        ))}
      </div>

      <div>
        {tab === "Plan" && <AgentTimeline agentId={agent.id} />}
        {tab === "Memory" && <AgentMemoryView agentId={agent.id} />}
        {tab === "Collaboration" && <AgentCollaborationView agentId={agent.id} />}
        {tab === "Guardrails" && <AgentGuardrailsConfig agent={agent} onSaved={() => void reload()} />}
      </div>
    </div>
  );
}
