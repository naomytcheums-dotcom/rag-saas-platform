"use client";

import { DatasetValidate } from "@/components/fine-tuning/DatasetValidate";
import type { FineTuningDataset } from "@/lib/services/fine-tuning";

const STYLES: Record<string, string> = {
  pending: "bg-surface-muted text-foreground-muted",
  validating: "bg-warning-soft text-warning",
  ready: "bg-success-soft text-success",
  error: "bg-danger-soft text-danger",
};

interface DatasetCardProps {
  dataset: FineTuningDataset;
  onDelete: (id: string) => void;
  onValidated: () => void;
}

export function DatasetCard({ dataset, onDelete, onValidated }: DatasetCardProps) {
  return (
    <div className="rounded-xl border border-border bg-surface p-4">
      <div className="flex items-center justify-between">
        <span className="text-sm font-medium text-foreground">{dataset.name}</span>
        <span className={`rounded-full px-2 py-0.5 text-xs font-medium ${STYLES[dataset.status] ?? STYLES.pending}`}>{dataset.status}</span>
      </div>
      {dataset.description && <p className="mt-1 text-xs text-foreground-muted">{dataset.description}</p>}
      <div className="mt-2 flex gap-3 text-xs text-foreground-muted">
        <span>{dataset.format}</span>
        <span>{(dataset.size / 1024).toFixed(0)} KB</span>
        {dataset.example_count != null && <span>{dataset.example_count} examples</span>}
      </div>
      {dataset.validation_errors && dataset.validation_errors.length > 0 && (
        <ul className="mt-2 max-h-24 overflow-y-auto text-xs text-danger">
          {dataset.validation_errors.slice(0, 5).map((err, i) => (
            <li key={i}>{err.line != null ? `Line ${err.line}: ` : ""}{err.error}</li>
          ))}
        </ul>
      )}
      <div className="mt-3 flex gap-2">
        <DatasetValidate datasetId={dataset.id} onValidated={onValidated} />
        <button type="button" onClick={() => onDelete(dataset.id)} className="rounded-lg border border-danger px-3 py-1 text-xs font-medium text-danger hover:bg-danger-soft">
          Delete
        </button>
      </div>
    </div>
  );
}
