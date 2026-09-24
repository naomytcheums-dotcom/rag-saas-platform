"use client";

import Link from "next/link";
import { useEvalDatasets } from "@/lib/hooks/useEvalDatasets";

export function DatasetList({ orgId }: { orgId: string }) {
  const { datasets, loading, error, remove } = useEvalDatasets(orgId);

  if (loading) return <p className="text-sm text-foreground-muted">Loading…</p>;
  if (error) return <p className="rounded-lg bg-danger-soft px-3 py-2 text-sm text-danger">{error}</p>;
  if (datasets.length === 0) return <p className="rounded-xl border border-border bg-surface p-5 text-sm text-foreground-muted">No evaluation datasets yet.</p>;

  return (
    <div className="flex flex-col gap-3">
      {datasets.map((dataset) => (
        <div key={dataset.id} className="flex items-center justify-between rounded-xl border border-border bg-surface p-4">
          <Link href={`/dashboard/eval/${dataset.id}`} className="min-w-0 flex-1">
            <h3 className="text-sm font-medium text-foreground">{dataset.name}</h3>
            {dataset.description && <p className="mt-1 truncate text-xs text-foreground-muted">{dataset.description}</p>}
            <p className="mt-1 text-xs text-foreground-muted">v{dataset.version} · {dataset.is_active ? "active" : "inactive"}</p>
          </Link>
          <button
            type="button"
            onClick={() => { if (confirm(`Delete dataset "${dataset.name}"?`)) void remove(dataset.id); }}
            className="ml-4 rounded-lg px-3 py-1.5 text-xs font-medium text-danger hover:bg-danger-soft"
          >
            Delete
          </button>
        </div>
      ))}
    </div>
  );
}
