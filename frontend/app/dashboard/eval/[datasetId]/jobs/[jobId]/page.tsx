"use client";

import { use } from "react";
import Link from "next/link";
import { FailureAnalysis } from "@/components/eval/FailureAnalysis";
import { JobMetrics } from "@/components/eval/JobMetrics";
import { JobResults } from "@/components/eval/JobResults";
import { useEvalJob } from "@/lib/hooks/useEvalJobs";

export default function Page({ params }: { params: Promise<{ datasetId: string; jobId: string }> }) {
  const { datasetId, jobId } = use(params);
  const { job, loading, error, cancel } = useEvalJob(jobId);

  if (loading) return <p className="mx-auto max-w-4xl text-sm text-foreground-muted">Loading…</p>;
  if (error) return <p className="mx-auto max-w-4xl rounded-lg bg-danger-soft px-3 py-2 text-sm text-danger">{error}</p>;
  if (!job) return null;

  return (
    <div className="mx-auto flex max-w-4xl flex-col gap-8">
      <div>
        <Link href={`/dashboard/eval/${datasetId}`} className="text-xs text-foreground-muted hover:underline">← Dataset</Link>
        <div className="mt-1 flex items-center justify-between">
          <h1 className="text-xl font-semibold text-foreground">Run {job.id.slice(0, 8)}</h1>
          {(job.status === "pending" || job.status === "running") && (
            <button type="button" onClick={() => void cancel()} className="rounded-lg border border-border px-3 py-1.5 text-xs font-medium text-danger hover:bg-danger-soft">
              Cancel
            </button>
          )}
        </div>
      </div>

      <JobMetrics job={job} />

      <div>
        <h2 className="mb-3 text-sm font-semibold text-foreground">Results</h2>
        <JobResults jobId={jobId} />
      </div>

      <div>
        <h2 className="mb-3 text-sm font-semibold text-foreground">Failure analysis</h2>
        <FailureAnalysis jobId={jobId} />
      </div>
    </div>
  );
}
