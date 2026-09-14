"use client";

import { useState } from "react";
import * as fineTuningService from "@/lib/services/fine-tuning";

export function DatasetValidate({ datasetId, onValidated }: { datasetId: string; onValidated: () => void }) {
  const [validating, setValidating] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const run = async () => {
    setValidating(true);
    setError(null);
    try {
      await fineTuningService.validateDataset(datasetId);
      onValidated();
    } catch (err) {
      setError(err instanceof Error ? err.message : "Validation failed");
    } finally {
      setValidating(false);
    }
  };

  return (
    <div className="flex items-center gap-2">
      <button type="button" onClick={() => void run()} disabled={validating} className="rounded-lg border border-border px-3 py-1 text-xs font-medium text-foreground hover:bg-surface-muted disabled:opacity-50">
        {validating ? "Validating…" : "Re-validate"}
      </button>
      {error && <span className="text-xs text-danger">{error}</span>}
    </div>
  );
}
