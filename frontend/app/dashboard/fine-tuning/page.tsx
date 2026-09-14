"use client";

import Link from "next/link";
import { useFineTuningDatasets } from "@/lib/hooks/useFineTuningDatasets";
import { useFineTuningJobs } from "@/lib/hooks/useFineTuningJobs";
import { useFineTunedModels } from "@/lib/hooks/useFineTunedModels";
import { useCurrentOrg } from "@/lib/useCurrentOrg";

function SummaryCard({ href, title, total, loading }: { href: string; title: string; total: number; loading: boolean }) {
  return (
    <Link href={href} className="block rounded-xl border border-border bg-surface p-5 hover:border-accent">
      <p className="text-sm text-foreground-muted">{title}</p>
      <p className="mt-1 text-2xl font-semibold text-foreground">{loading ? "…" : total}</p>
    </Link>
  );
}

export default function Page() {
  const { org, loading: orgLoading } = useCurrentOrg();
  const { total: datasetTotal, loading: datasetsLoading } = useFineTuningDatasets(org?.id ?? "");
  const { total: jobTotal, loading: jobsLoading } = useFineTuningJobs(org?.id ?? "");
  const { total: modelTotal, loading: modelsLoading } = useFineTunedModels(org?.id ?? "");

  if (orgLoading || !org) return <p className="mx-auto max-w-4xl text-sm text-foreground-muted">Loading…</p>;

  return (
    <div className="mx-auto max-w-4xl">
      <h1 className="text-xl font-semibold text-foreground">Fine-tuning</h1>
      <p className="mt-1 text-sm text-foreground-muted">Train custom models on your own data, evaluate them, and deploy the ones that work.</p>

      <div className="mt-5 grid grid-cols-1 gap-3 sm:grid-cols-3">
        <SummaryCard href="/dashboard/fine-tuning/datasets" title="Datasets" total={datasetTotal} loading={datasetsLoading} />
        <SummaryCard href="/dashboard/fine-tuning/jobs" title="Jobs" total={jobTotal} loading={jobsLoading} />
        <SummaryCard href="/dashboard/fine-tuning/models" title="Models" total={modelTotal} loading={modelsLoading} />
      </div>
    </div>
  );
}
