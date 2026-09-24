"use client";

import Link from "next/link";
import { useEvalJobs } from "@/lib/hooks/useEvalJobs";

const STATUS_COLOR: Record<string, string> = {
  pending: "text-foreground-muted",
  running: "text-accent",
  completed: "text-success",
  failed: "text-danger",
  cancelled: "text-foreground-muted",
};

export function JobList({ datasetId }: { datasetId: string }) {
  const { jobs, loading, error, launch } = useEvalJobs(datasetId);

  return (
    <div className="flex flex-col gap-3">
      <div className="flex items-center justify-between">
        <h2 className="text-sm font-semibold text-foreground">Runs</h2>
        <button type="button" onClick={() => void launch()} className="rounded-lg bg-accent px-3 py-1.5 text-xs font-medium text-white hover:bg-accent-hover">
          Launch run
        </button>
      </div>

      {loading ? (
        <p className="text-sm text-foreground-muted">Loading…</p>
      ) : error ? (
        <p className="rounded-lg bg-danger-soft px-3 py-2 text-sm text-danger">{error}</p>
      ) : jobs.length === 0 ? (
        <p className="rounded-xl border border-border bg-surface p-5 text-sm text-foreground-muted">No runs yet.</p>
      ) : (
        <div className="flex flex-col gap-2">
          {jobs.map((job) => (
            <Link key={job.id} href={`/dashboard/eval/${datasetId}/jobs/${job.id}`} className="flex items-center justify-between rounded-xl border border-border bg-surface p-3 hover:border-accent">
              <div>
                <span className={`text-sm font-medium ${STATUS_COLOR[job.status] ?? "text-foreground"}`}>{job.status}</span>
                <span className="ml-3 text-xs text-foreground-muted">{job.completed_questions}/{job.total_questions} questions</span>
              </div>
              <span className="text-xs text-foreground-muted">{new Date(job.created_at).toLocaleString()}</span>
            </Link>
          ))}
        </div>
      )}
    </div>
  );
}
