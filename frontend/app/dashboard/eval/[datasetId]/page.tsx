"use client";

import { use, useEffect, useState } from "react";
import Link from "next/link";
import { JobList } from "@/components/eval/JobList";
import { QuestionList } from "@/components/eval/QuestionList";
import * as evalService from "@/lib/services/eval";
import type { EvalDataset } from "@/lib/services/eval";

export default function Page({ params }: { params: Promise<{ datasetId: string }> }) {
  const { datasetId } = use(params);
  const [dataset, setDataset] = useState<EvalDataset | null>(null);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    let cancelled = false;
    evalService.getDataset(datasetId).then((d) => { if (!cancelled) setDataset(d); })
      .catch((err) => { if (!cancelled) setError(err instanceof Error ? err.message : "Failed to load dataset"); });
    return () => { cancelled = true; };
  }, [datasetId]);

  if (error) return <p className="mx-auto max-w-4xl rounded-lg bg-danger-soft px-3 py-2 text-sm text-danger">{error}</p>;
  if (!dataset) return <p className="mx-auto max-w-4xl text-sm text-foreground-muted">Loading…</p>;

  return (
    <div className="mx-auto flex max-w-4xl flex-col gap-8">
      <div>
        <Link href="/dashboard/eval" className="text-xs text-foreground-muted hover:underline">← Datasets</Link>
        <h1 className="mt-1 text-xl font-semibold text-foreground">{dataset.name}</h1>
        {dataset.description && <p className="mt-1 text-sm text-foreground-muted">{dataset.description}</p>}
      </div>

      <QuestionList datasetId={datasetId} />
      <JobList datasetId={datasetId} />
    </div>
  );
}
