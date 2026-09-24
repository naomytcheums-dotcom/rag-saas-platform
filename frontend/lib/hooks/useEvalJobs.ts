"use client";

import { useCallback, useEffect, useState } from "react";
import * as evalService from "@/lib/services/eval";
import type { EvalJob } from "@/lib/services/eval";

export function useEvalJobs(datasetId: string) {
  const [jobs, setJobs] = useState<EvalJob[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  const reload = useCallback(async () => {
    setLoading(true);
    try {
      const response = await evalService.listJobs(datasetId);
      setJobs(response.items);
      setError(null);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Failed to load runs");
    } finally {
      setLoading(false);
    }
  }, [datasetId]);

  useEffect(() => {
    // eslint-disable-next-line react-hooks/set-state-in-effect -- syncing with the backend after mount/dataset change
    void reload();
  }, [reload]);

  const launch = useCallback(async () => {
    const job = await evalService.createJob(datasetId);
    await reload();
    return job;
  }, [datasetId, reload]);

  return { jobs, loading, error, reload, launch };
}

/**
 * Real, polling-based progress (no SSE endpoint exists yet for job
 * progress -- api/routers/evaluation_jobs.py only exposes GET
 * /jobs/{id}, no stream). Polls every 2s only while the job is still
 * pending/running, and stops itself once it reaches a terminal status
 * -- never polls a completed/failed/cancelled job forever.
 */
export function useEvalJob(jobId: string) {
  const [job, setJob] = useState<EvalJob | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  const reload = useCallback(async () => {
    try {
      const data = await evalService.getJob(jobId);
      setJob(data);
      setError(null);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Failed to load run");
    } finally {
      setLoading(false);
    }
  }, [jobId]);

  useEffect(() => {
    // eslint-disable-next-line react-hooks/set-state-in-effect -- syncing with the backend after mount/job change
    void reload();
  }, [reload]);

  useEffect(() => {
    if (!job || job.status === "completed" || job.status === "failed" || job.status === "cancelled") return;
    const interval = setInterval(() => void reload(), 2000);
    return () => clearInterval(interval);
  }, [job, reload]);

  const cancel = useCallback(async () => {
    await evalService.cancelJob(jobId);
    await reload();
  }, [jobId, reload]);

  return { job, loading, error, reload, cancel };
}
