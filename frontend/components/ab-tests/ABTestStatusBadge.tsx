"use client";

const STYLES: Record<string, string> = {
  draft: "bg-surface-muted text-foreground-muted",
  running: "bg-success-soft text-success",
  paused: "bg-warning-soft text-warning",
  completed: "bg-accent-soft text-accent",
};

export function ABTestStatusBadge({ status }: { status: string }) {
  return <span className={`rounded-full px-2 py-0.5 text-xs font-medium ${STYLES[status] ?? STYLES.draft}`}>{status}</span>;
}
