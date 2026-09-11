"use client";

import { useEffect, useState } from "react";
import { api, ApiError } from "@/lib/api";
import type { IntegrationLog } from "@/lib/types";

interface IntegrationLogsProps {
  orgId: string;
  connectionId: string;
  onError: (message: string) => void;
}

// Partie 15.1 -- GET .../connections/{id}/logs: the real receipt log
// of every inbound POST this connection has received, whether
// accepted, rejected, or errored.
export default function IntegrationLogs({ orgId, connectionId, onError }: IntegrationLogsProps) {
  const [logs, setLogs] = useState<IntegrationLog[]>([]);
  const [expanded, setExpanded] = useState<string | null>(null);

  useEffect(() => {
    void api
      .get<IntegrationLog[]>(`/organizations/${orgId}/integrations/connections/${connectionId}/logs`)
      .then(setLogs)
      .catch((err) => onError(err instanceof ApiError ? String(err.detail) : "Failed to load logs"));
  }, [orgId, connectionId, onError]);

  return (
    <div className="rounded-lg border border-border bg-background p-3 text-xs">
      <h4 className="font-medium text-foreground">Receipt log</h4>
      <div className="mt-2 flex flex-col gap-1">
        {logs.map((log) => (
          <div key={log.id}>
            <button type="button" onClick={() => setExpanded(expanded === log.id ? null : log.id)} className="w-full text-left text-foreground-muted hover:text-foreground">
              <span className={log.status === "error" ? "text-danger" : log.status === "rejected" ? "text-warning" : "text-foreground"}>{log.status}</span>
              {" — "}{new Date(log.created_at).toLocaleString()}{log.detail ? ` — ${log.detail}` : ""}
            </button>
            {expanded === log.id && (
              <pre className="mt-1 overflow-x-auto rounded bg-surface p-2 font-mono text-foreground-muted">{JSON.stringify(log.payload, null, 2)}</pre>
            )}
          </div>
        ))}
        {logs.length === 0 && <p className="text-foreground-muted">No inbound payloads received yet.</p>}
      </div>
    </div>
  );
}
