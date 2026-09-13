"use client";

import type { AutonomousAgent } from "@/lib/services/autonomous-agents";

interface AgentRunPanelProps {
  agent: AutonomousAgent;
  onRun: () => void | Promise<void>;
  onPause: () => void | Promise<void>;
  onResume: () => void | Promise<void>;
  onStop: () => void | Promise<void>;
}

export function AgentRunPanel({ agent, onRun, onPause, onResume, onStop }: AgentRunPanelProps) {
  const canRun = agent.status === "idle" || agent.status === "error" || agent.status === "completed";
  const canPause = agent.status === "planning" || agent.status === "executing";
  const canResume = agent.status === "paused";
  const canStop = agent.status !== "idle";

  return (
    <div className="flex flex-wrap gap-2">
      {canRun && (
        <button type="button" onClick={() => void onRun()} className="rounded-lg bg-accent px-4 py-2 text-sm font-medium text-white hover:bg-accent-hover">
          Run
        </button>
      )}
      {canPause && (
        <button type="button" onClick={() => void onPause()} className="rounded-lg border border-border px-4 py-2 text-sm font-medium text-foreground hover:bg-surface-muted">
          Pause
        </button>
      )}
      {canResume && (
        <button type="button" onClick={() => void onResume()} className="rounded-lg bg-accent px-4 py-2 text-sm font-medium text-white hover:bg-accent-hover">
          Resume
        </button>
      )}
      {canStop && (
        <button type="button" onClick={() => void onStop()} className="rounded-lg border border-danger px-4 py-2 text-sm font-medium text-danger hover:bg-danger-soft">
          Stop
        </button>
      )}
    </div>
  );
}
