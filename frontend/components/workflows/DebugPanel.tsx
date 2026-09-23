"use client";

// Phase 5, Étape 5 -- real debug/run panel: triggers a real run
// (POST /workflows/{id}/run), then streams REAL execution events over
// SSE (api/services/workflow_engine.py's own node_started/
// node_completed/waiting_human/run_completed/run_failed events,
// api/routers/workflows.py's own GET /workflows/runs/{id}/stream).

import { useEffect, useRef, useState } from "react";
import * as workflowService from "@/lib/services/workflows";

interface RunEvent {
  event: string;
  node_id: string | null;
  status?: string;
  output?: unknown;
  error?: string;
}

interface Props {
  workflowId: string;
  onCurrentNodeChange: (nodeId: string | null) => void;
  onRunStarted?: () => void;
}

export function DebugPanel({ workflowId, onCurrentNodeChange, onRunStarted }: Props) {
  const [running, setRunning] = useState(false);
  const [events, setEvents] = useState<RunEvent[]>([]);
  const [runId, setRunId] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);
  const stopRef = useRef<(() => void) | null>(null);

  useEffect(() => () => stopRef.current?.(), []);

  const handleRun = async () => {
    setError(null);
    setEvents([]);
    setRunning(true);
    try {
      const run = await workflowService.runWorkflow(workflowId, {});
      setRunId(run.id);
      onRunStarted?.();
      stopRef.current = workflowService.streamWorkflowRun(
        run.id,
        (raw) => {
          const event = raw as unknown as RunEvent;
          setEvents((prev) => [...prev, event]);
          onCurrentNodeChange(event.node_id ?? null);
          if (event.event === "run_completed" || event.event === "run_failed" || event.event === "waiting_human") {
            setRunning(false);
          }
        },
        () => setRunning(false),
      );
    } catch (err) {
      setError(err instanceof Error ? err.message : "Failed to start run");
      setRunning(false);
    }
  };

  return (
    <div className="border-t border-border p-3" data-testid="debug-panel">
      <div className="flex items-center justify-between">
        <h3 className="text-xs font-semibold text-foreground">Debug / Exécution</h3>
        <button
          type="button"
          onClick={() => void handleRun()}
          disabled={running}
          className="rounded-md bg-accent px-3 py-1 text-xs font-medium text-white hover:bg-accent-hover disabled:opacity-50"
          data-testid="run-button"
        >
          {running ? "En cours…" : "Lancer"}
        </button>
      </div>
      {runId && <p className="mt-1 text-[11px] text-foreground-muted">Run: {runId}</p>}
      {error && <p className="mt-1 text-xs text-danger">{error}</p>}
      <ul className="mt-2 max-h-48 space-y-1 overflow-y-auto text-[11px]" data-testid="debug-log">
        {events.map((event, index) => (
          <li key={index} className="rounded bg-surface-muted px-2 py-1 text-foreground-muted">
            <span className="font-medium text-foreground">{event.event}</span>
            {event.node_id ? ` — ${event.node_id}` : ""}
            {event.error ? ` — ${event.error}` : ""}
          </li>
        ))}
      </ul>
    </div>
  );
}
