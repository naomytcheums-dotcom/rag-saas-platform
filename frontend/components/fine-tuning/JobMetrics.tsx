"use client";

import type { FineTuningJob } from "@/lib/services/fine-tuning";

export function JobMetrics({ job }: { job: FineTuningJob }) {
  const entries = Object.entries(job.metrics || {});
  if (entries.length === 0) return <p className="text-xs text-foreground-muted">No metrics yet.</p>;

  return (
    <dl className="grid grid-cols-2 gap-3 sm:grid-cols-3">
      {entries.map(([key, value]) => (
        <div key={key} className="rounded-lg border border-border bg-surface p-3">
          <dt className="text-xs text-foreground-muted">{key}</dt>
          <dd className="text-sm font-medium text-foreground">{String(value)}</dd>
        </div>
      ))}
    </dl>
  );
}
