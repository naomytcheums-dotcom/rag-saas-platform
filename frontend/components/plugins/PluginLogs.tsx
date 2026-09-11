"use client";

import { useCallback, useEffect, useState } from "react";
import { ApiError } from "@/lib/api";
import { executePlugin, listPluginExecutions } from "@/lib/services/plugins";
import type { PluginExecution } from "@/lib/types";

interface PluginLogsProps {
  orgId: string;
  pluginId: string;
  onError?: (message: string) => void;
}

const STATUS_CLASS: Record<PluginExecution["status"], string> = {
  success: "text-success",
  error: "text-danger",
  timeout: "text-warning",
};

// Partie 16 (ter) -- GET .../executions (real PluginExecution history)
// + a manual "Run" button against POST .../execute, api/security/
// plugin_sandbox.py's own real sandboxed run.
export default function PluginLogs({ orgId, pluginId, onError }: PluginLogsProps) {
  const [executions, setExecutions] = useState<PluginExecution[]>([]);
  const [running, setRunning] = useState(false);
  const [expanded, setExpanded] = useState<string | null>(null);

  const load = useCallback(async () => {
    try {
      setExecutions(await listPluginExecutions(orgId, pluginId));
    } catch (err) {
      onError?.(err instanceof ApiError ? String(err.detail) : "Failed to load execution logs");
    }
  }, [orgId, pluginId, onError]);

  useEffect(() => {
    // eslint-disable-next-line react-hooks/set-state-in-effect
    void load();
  }, [load]);

  async function run() {
    setRunning(true);
    try {
      await executePlugin(orgId, pluginId, {});
      await load();
    } catch (err) {
      onError?.(err instanceof ApiError ? String(err.detail) : "Failed to run this plugin");
    } finally {
      setRunning(false);
    }
  }

  return (
    <div className="rounded-lg border border-border bg-background p-3 text-xs">
      <div className="flex items-center justify-between">
        <h4 className="font-medium text-foreground">Execution log</h4>
        <button type="button" onClick={() => void run()} disabled={running} className="rounded-lg bg-accent px-2.5 py-1 text-xs font-medium text-white hover:bg-accent-hover disabled:opacity-50">
          {running ? "Running…" : "Run now"}
        </button>
      </div>
      <div className="mt-2 flex flex-col gap-1">
        {executions.map((execution) => (
          <div key={execution.id}>
            <button type="button" onClick={() => setExpanded(expanded === execution.id ? null : execution.id)} className="w-full text-left text-foreground-muted hover:text-foreground">
              <span className={STATUS_CLASS[execution.status]}>{execution.status}</span>
              {" — "}{new Date(execution.created_at).toLocaleString()}
              {execution.duration_ms !== null ? ` — ${execution.duration_ms}ms` : ""}
              {execution.hook ? ` — hook: ${execution.hook}` : ""}
            </button>
            {expanded === execution.id && (
              <pre className="mt-1 overflow-x-auto rounded bg-surface p-2 font-mono text-foreground-muted">
                {JSON.stringify({ input: execution.input_payload, output: execution.output_payload, error: execution.error_message }, null, 2)}
              </pre>
            )}
          </div>
        ))}
        {executions.length === 0 && <p className="text-foreground-muted">No executions yet.</p>}
      </div>
    </div>
  );
}
