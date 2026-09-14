"use client";

import { useEffect, useState } from "react";
import { JobMetrics } from "@/components/fine-tuning/JobMetrics";
import * as fineTuningService from "@/lib/services/fine-tuning";
import type { FineTuningJob } from "@/lib/services/fine-tuning";

const ACTIVE_STATUSES = new Set(["pending", "running"]);
const POLL_INTERVAL_MS = 5000;

export function JobDetail({ jobId }: { jobId: string }) {
  const [job, setJob] = useState<FineTuningJob | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [cancelling, setCancelling] = useState(false);

  useEffect(() => {
    let cancelled = false;
    let timer: ReturnType<typeof setTimeout> | undefined;

    async function poll() {
      try {
        const current = await fineTuningService.getJob(jobId);
        if (cancelled) return;
        setJob(current);
        if (ACTIVE_STATUSES.has(current.status)) timer = setTimeout(poll, POLL_INTERVAL_MS);
      } catch (err) {
        if (!cancelled) setError(err instanceof Error ? err.message : "Failed to load job");
      }
    }

    void poll();
    return () => { cancelled = true; if (timer) clearTimeout(timer); };
  }, [jobId]);

  const cancelRun = async () => {
    setCancelling(true);
    try {
      setJob(await fineTuningService.cancelJob(jobId));
    } finally {
      setCancelling(false);
    }
  };

  if (error) return <p className="rounded-lg bg-danger-soft px-3 py-2 text-sm text-danger">{error}</p>;
  if (!job) return <p className="text-sm text-foreground-muted">Loading…</p>;

  return (
    <div className="flex flex-col gap-4">
      <div className="flex items-center justify-between">
        <h1 className="text-lg font-semibold text-foreground">{job.name}</h1>
        <span className="text-sm text-foreground-muted">{job.status}</span>
      </div>
      <p className="text-sm text-foreground-muted">{job.provider} — {job.base_model}</p>
      {job.error_message && <p className="rounded-lg bg-danger-soft px-3 py-2 text-sm text-danger">{job.error_message}</p>}
      {ACTIVE_STATUSES.has(job.status) && (
        <button type="button" onClick={() => void cancelRun()} disabled={cancelling} className="self-start rounded-lg border border-danger px-4 py-2 text-sm font-medium text-danger hover:bg-danger-soft disabled:opacity-50">
          {cancelling ? "Cancelling…" : "Cancel job"}
        </button>
      )}
      <section>
        <h2 className="text-sm font-semibold text-foreground">Metrics</h2>
        <div className="mt-2"><JobMetrics job={job} /></div>
      </section>
    </div>
  );
}
