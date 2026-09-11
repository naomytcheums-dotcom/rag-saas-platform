"use client";

import { useState } from "react";
import { api } from "@/lib/api";
import type { UniversalConnection } from "@/lib/types";
import ConnectionTest from "./ConnectionTest";
import IntegrationLogs from "./IntegrationLogs";
import MappingList from "./MappingList";
import SyncHistory from "./SyncHistory";
import WebhookConfig from "./WebhookConfig";

interface ConnectionItemProps {
  orgId: string;
  connection: UniversalConnection;
  revealedToken?: string;
  onDeleted: (id: string) => void;
  onError: (message: string) => void;
}

// Partie 15.1 -- one real IntegrationConnection row, expandable into
// its own webhook config / mapping / test / sync / log panels rather
// than a separate page per connection.
export default function ConnectionItem({ orgId, connection, revealedToken, onDeleted, onError }: ConnectionItemProps) {
  const [expanded, setExpanded] = useState(false);

  async function remove() {
    await api.delete(`/organizations/${orgId}/integrations/connections/${connection.id}`);
    onDeleted(connection.id);
  }

  return (
    <div className="rounded-xl border border-border bg-surface p-3 text-sm">
      <div className="flex items-center justify-between">
        <button type="button" onClick={() => setExpanded((v) => !v)} className="text-left">
          <span className="font-medium text-foreground">{connection.name}</span>
          <span className="ml-2 text-xs text-foreground-muted">{connection.provider} → {connection.action}{connection.is_active ? "" : " (inactive)"}</span>
        </button>
        <div className="flex gap-3">
          <button type="button" onClick={() => setExpanded((v) => !v)} className="text-xs font-medium text-accent-hover hover:underline">{expanded ? "Collapse" : "Manage"}</button>
          <button type="button" onClick={() => void remove()} className="text-xs font-medium text-danger hover:underline">Delete</button>
        </div>
      </div>

      {expanded && (
        <div className="mt-3 flex flex-col gap-3">
          <WebhookConfig connectionId={connection.id} provider={connection.provider} token={revealedToken} />
          <MappingList orgId={orgId} connectionId={connection.id} onError={onError} />
          <ConnectionTest orgId={orgId} connectionId={connection.id} />
          <SyncHistory orgId={orgId} connectionId={connection.id} onError={onError} />
          <IntegrationLogs orgId={orgId} connectionId={connection.id} onError={onError} />
        </div>
      )}
    </div>
  );
}
