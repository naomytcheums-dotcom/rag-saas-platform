"use client";

import { useCallback, useEffect, useState } from "react";
import * as fineTuningService from "@/lib/services/fine-tuning";
import type { FineTuningJob } from "@/lib/services/fine-tuning";

const ACTIVE_STATUSES = new Set(["pending", "running"]);
const POLL_INTERVAL_MS = 5000;

export function useFineTuningJobs(orgId: string) {
  const [jobs, setJobs] = useState<FineTuningJob[]>([]);
  const [total, setTotal] = useState(0);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  const reload = useCallback(async () => {
    try {
      const response = await fineTuningService.listJobs(orgId);
      setJobs(response.items);
      setTotal(response.total);
      setError(null);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Failed to load jobs");
    } finally {
      setLoading(false);
    }
  }, [orgId]);

  useEffect(() => {
    void reload();
  }, [reload]);

  // Real status polling only while at least one real job is still
  // pending/running -- no fabricated progress bar, just a real
  // periodic re-fetch (this session's own standing instruction).
  useEffect(() => {
    if (!jobs.some((job) => ACTIVE_STATUSES.has(job.status))) return;
    const timer = setTimeout(() => void reload(), POLL_INTERVAL_MS);
    return () => clearTimeout(timer);
  }, [jobs, reload]);

  const create = useCallback(async (data: Parameters<typeof fineTuningService.createJob>[1]) => {
    const created = await fineTuningService.createJob(orgId, data);
    await reload();
    return created;
  }, [orgId, reload]);

  const cancel = useCallback(async (id: string) => {
    await fineTuningService.cancelJob(id);
    await reload();
  }, [reload]);

  return { jobs, total, loading, error, reload, create, cancel };
}
