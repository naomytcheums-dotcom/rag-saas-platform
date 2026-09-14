"use client";

import Link from "next/link";
import type { FineTuningJob } from "@/lib/services/fine-tuning";

const STYLES: Record<string, string> = {
  pending: "bg-surface-muted text-foreground-muted",
  running: "bg-warning-soft text-warning",
  succeeded: "bg-success-soft text-success",
  failed: "bg-danger-soft text-danger",
  cancelled: "bg-surface-muted text-foreground-muted",
};

export function JobCard({ job }: { job: FineTuningJob }) {
  return (
    <Link href={`/dashboard/fine-tuning/jobs/${job.id}`} className="block rounded-xl border border-border bg-surface p-4 hover:border-accent">
      <div className="flex items-center justify-between">
        <span className="text-sm font-medium text-foreground">{job.name}</span>
        <span className={`rounded-full px-2 py-0.5 text-xs font-medium ${STYLES[job.status] ?? STYLES.pending}`}>{job.status}</span>
      </div>
      <div className="mt-2 flex gap-3 text-xs text-foreground-muted">
        <span>{job.provider}</span>
        <span>{job.base_model}</span>
      </div>
      {job.error_message && <p className="mt-2 text-xs text-danger">{job.error_message}</p>}
    </Link>
  );
}
