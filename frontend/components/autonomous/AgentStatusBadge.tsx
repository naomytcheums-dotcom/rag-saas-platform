"use client";

const STYLES: Record<string, string> = {
  idle: "bg-surface-muted text-foreground-muted",
  planning: "bg-warning-soft text-warning",
  executing: "bg-warning-soft text-warning",
  paused: "bg-surface-muted text-foreground-muted",
  completed: "bg-success-soft text-success",
  error: "bg-danger-soft text-danger",
};

export function AgentStatusBadge({ status }: { status: string }) {
  return <span className={`rounded-full px-2 py-0.5 text-xs font-medium ${STYLES[status] ?? STYLES.idle}`}>{status}</span>;
}
