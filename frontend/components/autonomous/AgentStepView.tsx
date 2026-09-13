"use client";

import type { AgentStep } from "@/lib/services/autonomous-agents";

const STATUS_STYLES: Record<string, string> = {
  pending: "bg-surface-muted text-foreground-muted",
  running: "bg-warning-soft text-warning",
  completed: "bg-success-soft text-success",
  failed: "bg-danger-soft text-danger",
  skipped: "bg-surface-muted text-foreground-muted",
};

export function AgentStepView({ step }: { step: AgentStep }) {
  const description = (step.parameters as { description?: string } | null)?.description ?? "";
  return (
    <div className="rounded-lg border border-border bg-surface p-3">
      <div className="flex items-center justify-between">
        <span className="text-sm font-medium text-foreground">#{step.step_number} — {step.action}</span>
        <span className={`rounded-full px-2 py-0.5 text-xs font-medium ${STATUS_STYLES[step.status] ?? STATUS_STYLES.pending}`}>{step.status}</span>
      </div>
      {description && <p className="mt-1 text-xs text-foreground-muted">{description}</p>}
      {step.result && <p className="mt-1 text-xs text-foreground">{String((step.result as { output?: string }).output ?? "")}</p>}
      {step.error && <p className="mt-1 text-xs text-danger">{step.error}</p>}
    </div>
  );
}
