"use client";

const STYLES: Record<string, string> = {
  pending: "bg-surface-muted text-foreground-muted",
  processing: "bg-warning-soft text-warning",
  completed: "bg-success-soft text-success",
  failed: "bg-danger-soft text-danger",
};

export function MediaStatusBadge({ status }: { status: string }) {
  return <span className={`rounded-full px-2 py-0.5 text-xs font-medium ${STYLES[status] ?? STYLES.pending}`}>{status}</span>;
}
