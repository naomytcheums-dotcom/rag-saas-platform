"use client";

// Phase 5, Étape 5 -- real execution history list + detail, backed by
// the run-listing/detail endpoints this étape's own backend audit
// found missing and added (GET /workflows/{id}/runs, GET
// /workflows/runs/{run_id}).

import { useEffect, useState } from "react";
import { useWorkflowRuns } from "@/lib/hooks/useWorkflowRuns";
import type { WorkflowRun } from "@/lib/services/workflows";

const STATUS_STYLES: Record<string, string> = {
  pending: "bg-surface-muted text-foreground-muted",
  running: "bg-warning-soft text-warning",
  waiting_human: "bg-danger-soft text-danger",
  completed: "bg-success-soft text-success",
  failed: "bg-danger-soft text-danger",
};

function durationLabel(run: WorkflowRun): string {
  if (!run.completed_at) return "—";
  const ms = new Date(run.completed_at).getTime() - new Date(run.started_at).getTime();
  return `${(ms / 1000).toFixed(1)}s`;
}

export function ExecutionHistory({ workflowId, refreshSignal }: { workflowId: string; refreshSignal?: number }) {
  const { runs, loading, reload } = useWorkflowRuns(workflowId);
  const [selected, setSelected] = useState<WorkflowRun | null>(null);

  // A run started from DebugPanel (a sibling component) doesn't
  // otherwise reach this list -- `refreshSignal` is a real, simple
  // "something changed" counter WorkflowBuilder bumps via
  // DebugPanel's own onRunStarted, not polling on a timer.
  useEffect(() => {
    if (refreshSignal !== undefined) void reload();
    // eslint-disable-next-line react-hooks/exhaustive-deps -- deliberately re-runs only when refreshSignal changes, not on every `reload` identity change
  }, [refreshSignal]);

  if (loading) return <p className="p-3 text-xs text-foreground-muted">Chargement de l&apos;historique…</p>;

  return (
    <div className="border-t border-border p-3" data-testid="execution-history">
      <h3 className="text-xs font-semibold text-foreground">Historique d&apos;exécution</h3>
      {runs.length === 0 && <p className="mt-2 text-xs text-foreground-muted">Aucune exécution.</p>}
      <ul className="mt-2 space-y-1">
        {runs.map((run) => (
          <li key={run.id}>
            <button
              type="button"
              onClick={() => setSelected(run)}
              className="flex w-full items-center justify-between rounded px-2 py-1 text-left text-[11px] hover:bg-surface-muted"
              data-testid={`run-row-${run.id}`}
            >
              <span className={`rounded-full px-2 py-0.5 font-medium ${STATUS_STYLES[run.status] ?? ""}`}>{run.status}</span>
              <span className="text-foreground-muted">{durationLabel(run)}</span>
              <span className="text-foreground-muted">{new Date(run.started_at).toLocaleString()}</span>
            </button>
          </li>
        ))}
      </ul>
      {selected && (
        <div className="mt-3 rounded-md border border-border bg-surface-muted p-2 text-[11px]" data-testid="run-detail">
          <p><span className="font-medium">Statut :</span> {selected.status}</p>
          <p><span className="font-medium">Nœud courant :</span> {selected.current_node_id ?? "—"}</p>
          {selected.error && <p className="text-danger"><span className="font-medium">Erreur :</span> {selected.error}</p>}
          <pre className="mt-1 max-h-32 overflow-y-auto whitespace-pre-wrap break-all text-[10px]">{JSON.stringify(selected.context, null, 2)}</pre>
        </div>
      )}
    </div>
  );
}
