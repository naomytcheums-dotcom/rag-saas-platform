"use client";

import type { EvalJob } from "@/lib/services/eval";

function MetricCard({ label, value }: { label: string; value: string | number }) {
  return (
    <div className="rounded-xl border border-border bg-surface p-4">
      <p className="text-xs text-foreground-muted">{label}</p>
      <p className="mt-1 text-lg font-semibold text-foreground">{value}</p>
    </div>
  );
}

export function JobMetrics({ job }: { job: EvalJob }) {
  const failed = job.results?.failed_questions ?? 0;
  const succeeded = job.total_questions - failed;

  return (
    <div className="grid grid-cols-2 gap-3 sm:grid-cols-4">
      <MetricCard label="Status" value={job.status} />
      <MetricCard label="Progress" value={`${job.progress}%`} />
      <MetricCard label="Succeeded" value={succeeded} />
      <MetricCard label="Failed" value={failed} />
    </div>
  );
}
