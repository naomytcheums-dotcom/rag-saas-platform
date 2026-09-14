"use client";

import { DatasetCard } from "@/components/fine-tuning/DatasetCard";
import { useFineTuningDatasets } from "@/lib/hooks/useFineTuningDatasets";

export function DatasetList({ orgId }: { orgId: string }) {
  const { datasets, loading, error, reload, remove } = useFineTuningDatasets(orgId);

  if (loading) return <p className="text-sm text-foreground-muted">Loading…</p>;
  if (error) return <p className="rounded-lg bg-danger-soft px-3 py-2 text-sm text-danger">{error}</p>;
  if (datasets.length === 0) return <p className="rounded-xl border border-border bg-surface p-5 text-sm text-foreground-muted">No datasets yet.</p>;

  return (
    <div className="grid grid-cols-1 gap-3 sm:grid-cols-2">
      {datasets.map((dataset) => (
        <DatasetCard key={dataset.id} dataset={dataset} onDelete={(id) => void remove(id)} onValidated={() => void reload()} />
      ))}
    </div>
  );
}
