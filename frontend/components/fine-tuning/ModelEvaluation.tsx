"use client";

import { useEffect, useState } from "react";
import * as fineTuningService from "@/lib/services/fine-tuning";
import type { FineTuningEvaluation } from "@/lib/services/fine-tuning";

export function ModelEvaluation({ modelId }: { modelId: string }) {
  const [datasetId, setDatasetId] = useState("");
  const [evaluations, setEvaluations] = useState<FineTuningEvaluation[]>([]);
  const [running, setRunning] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const reload = () => {
    fineTuningService.listEvaluations(modelId).then(setEvaluations).catch(() => setEvaluations([]));
  };

  useEffect(reload, [modelId]);

  const run = async () => {
    if (!datasetId.trim()) return;
    setRunning(true);
    setError(null);
    try {
      await fineTuningService.evaluateModel(modelId, datasetId);
      setDatasetId("");
      reload();
    } catch (err) {
      setError(err instanceof Error ? err.message : "Evaluation failed");
    } finally {
      setRunning(false);
    }
  };

  return (
    <div className="flex flex-col gap-3">
      <div className="flex gap-2">
        <input
          value={datasetId} onChange={(e) => setDatasetId(e.target.value)} placeholder="Evaluation dataset id"
          className="flex-1 rounded-lg border border-border bg-background px-3 py-2 text-sm text-foreground"
        />
        <button type="button" onClick={() => void run()} disabled={running} className="rounded-lg bg-accent px-4 py-2 text-sm font-medium text-white hover:bg-accent-hover disabled:opacity-50">
          {running ? "Evaluating…" : "Evaluate"}
        </button>
      </div>
      {error && <p className="text-xs text-danger">{error}</p>}
      <div className="flex flex-col gap-2">
        {evaluations.map((evaluation) => (
          <div key={evaluation.id} className="rounded-lg border border-border bg-surface p-3">
            <div className="flex items-center justify-between">
              <span className="text-sm text-foreground">{new Date(evaluation.created_at).toLocaleString()}</span>
              <span className="text-sm font-medium text-foreground">{evaluation.score != null ? `${(evaluation.score * 100).toFixed(1)}%` : "—"}</span>
            </div>
          </div>
        ))}
      </div>
    </div>
  );
}
