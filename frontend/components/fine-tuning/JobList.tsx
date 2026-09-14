"use client";

import { JobCard } from "@/components/fine-tuning/JobCard";
import { useFineTuningJobs } from "@/lib/hooks/useFineTuningJobs";

export function JobList({ orgId }: { orgId: string }) {
  const { jobs, loading, error } = useFineTuningJobs(orgId);

  if (loading) return <p className="text-sm text-foreground-muted">Loading…</p>;
  if (error) return <p className="rounded-lg bg-danger-soft px-3 py-2 text-sm text-danger">{error}</p>;
  if (jobs.length === 0) return <p className="rounded-xl border border-border bg-surface p-5 text-sm text-foreground-muted">No fine-tuning jobs yet.</p>;

  return (
    <div className="grid grid-cols-1 gap-3 sm:grid-cols-2">
      {jobs.map((job) => <JobCard key={job.id} job={job} />)}
    </div>
  );
}
