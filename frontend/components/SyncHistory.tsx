"use client";

import { useCallback, useEffect, useState } from "react";
import { api, ApiError } from "@/lib/api";
import type { IntegrationLog } from "@/lib/types";

interface SyncHistoryProps {
  orgId: string;
  connectionId: string;
  onError: (message: string) => void;
}

// Partie 15.1/15.2 -- GET .../connections/{id}/syncs (an alias over
// this connection's own log ledger) and POST .../sync (re-runs the
// connection's current action against every previously failed
// payload -- see api/services/integrations.py's own retry_failed_logs
// docstring for why "sync" means this for a push-only connection).
export default function SyncHistory({ orgId, connectionId, onError }: SyncHistoryProps) {
  const [syncs, setSyncs] = useState<IntegrationLog[]>([]);
  const [syncing, setSyncing] = useState(false);

  const load = useCallback(async () => {
    try {
      setSyncs(await api.get<IntegrationLog[]>(`/organizations/${orgId}/integrations/connections/${connectionId}/syncs`));
    } catch (err) {
      onError(err instanceof ApiError ? String(err.detail) : "Failed to load sync history");
    }
  }, [orgId, connectionId, onError]);

  useEffect(() => {
    // eslint-disable-next-line react-hooks/set-state-in-effect
    void load();
  }, [load]);

  async function retrySync() {
    setSyncing(true);
    try {
      await api.post(`/organizations/${orgId}/integrations/connections/${connectionId}/sync`);
      await load();
    } catch (err) {
      onError(err instanceof ApiError ? String(err.detail) : "Sync failed");
    } finally {
      setSyncing(false);
    }
  }

  return (
    <div className="rounded-lg border border-border bg-background p-3 text-xs">
      <div className="flex items-center justify-between">
        <h4 className="font-medium text-foreground">Sync history</h4>
        <button type="button" onClick={() => void retrySync()} disabled={syncing} className="rounded-lg bg-accent px-2.5 py-1 text-xs font-medium text-white hover:bg-accent-hover disabled:opacity-50">
          {syncing ? "Retrying…" : "Retry failed"}
        </button>
      </div>
      <div className="mt-2 flex flex-col gap-1">
        {syncs.slice(0, 10).map((log) => (
          <p key={log.id} className="text-foreground-muted">
            <span className={log.status === "error" ? "text-danger" : "text-foreground"}>{log.status}</span> — {new Date(log.created_at).toLocaleString()}
          </p>
        ))}
        {syncs.length === 0 && <p className="text-foreground-muted">No syncs yet.</p>}
      </div>
    </div>
  );
}
