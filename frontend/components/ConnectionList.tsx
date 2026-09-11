"use client";

import { useCallback, useEffect, useState } from "react";
import { api, ApiError } from "@/lib/api";
import type { UniversalConnection } from "@/lib/types";
import ConnectionForm from "./ConnectionForm";
import ConnectionItem from "./ConnectionItem";

interface ConnectionListProps {
  orgId: string;
  onError: (message: string) => void;
}

// Partie 15.1/15.2 -- GET/POST/DELETE .../integrations/connections,
// the real replacement for this file's own former inline
// UniversalIntegrationsSection (now split into the 11 real components
// named in this étape's own spec).
export default function ConnectionList({ orgId, onError }: ConnectionListProps) {
  const [connections, setConnections] = useState<UniversalConnection[]>([]);
  const [revealedToken, setRevealedToken] = useState<{ id: string; token: string } | null>(null);

  const load = useCallback(async () => {
    try {
      setConnections(await api.get<UniversalConnection[]>(`/organizations/${orgId}/integrations/connections`));
    } catch (err) {
      onError(err instanceof ApiError ? String(err.detail) : "Failed to load integration connections");
    }
  }, [orgId, onError]);

  useEffect(() => {
    // eslint-disable-next-line react-hooks/set-state-in-effect
    void load();
  }, [load]);

  function handleCreated(created: UniversalConnection) {
    setRevealedToken(created.token ? { id: created.id, token: created.token } : null);
    void load();
  }

  function handleDeleted(id: string) {
    if (revealedToken?.id === id) setRevealedToken(null);
    void load();
  }

  return (
    <div className="rounded-xl border border-border bg-surface p-4">
      <h2 className="text-sm font-semibold text-foreground">Zapier / Make / n8n / custom webhooks</h2>
      <p className="mt-1 text-xs text-foreground-muted">
        Create a connection, then point your Zapier action, Make scenario, n8n workflow, or any CRM&apos;s outgoing webhook
        at the URL shown for it — with the token as a Bearer header.
      </p>

      <div className="mt-3 flex flex-col gap-2">
        {connections.map((connection) => (
          <ConnectionItem
            key={connection.id}
            orgId={orgId}
            connection={connection}
            revealedToken={revealedToken?.id === connection.id ? revealedToken.token : undefined}
            onDeleted={handleDeleted}
            onError={onError}
          />
        ))}
        {connections.length === 0 && <p className="text-xs text-foreground-muted">No connections yet.</p>}
      </div>

      <div className="mt-3">
        <ConnectionForm orgId={orgId} onCreated={handleCreated} onError={onError} />
      </div>
    </div>
  );
}
