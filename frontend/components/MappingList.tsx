"use client";

import { useCallback, useEffect, useState } from "react";
import { api, ApiError } from "@/lib/api";
import type { IntegrationMapping } from "@/lib/types";
import MappingEditor from "./MappingEditor";

interface MappingListProps {
  orgId: string;
  connectionId: string;
  onError: (message: string) => void;
}

// Partie 15.1 -- GET .../connections/{id}/mappings + delete, and the
// create/edit sub-form (MappingEditor).
export default function MappingList({ orgId, connectionId, onError }: MappingListProps) {
  const [mappings, setMappings] = useState<IntegrationMapping[]>([]);
  const [editingId, setEditingId] = useState<string | null>(null);

  const load = useCallback(async () => {
    try {
      setMappings(await api.get<IntegrationMapping[]>(`/organizations/${orgId}/integrations/connections/${connectionId}/mappings`));
    } catch (err) {
      onError(err instanceof ApiError ? String(err.detail) : "Failed to load mappings");
    }
  }, [orgId, connectionId, onError]);

  useEffect(() => {
    // eslint-disable-next-line react-hooks/set-state-in-effect
    void load();
  }, [load]);

  async function remove(id: string) {
    await api.delete(`/organizations/${orgId}/integrations/mappings/${id}`);
    await load();
  }

  return (
    <div className="rounded-lg border border-border bg-background p-3 text-xs">
      <h4 className="font-medium text-foreground">Field mappings</h4>

      <div className="mt-2 flex flex-col gap-2">
        {mappings.map((mapping) =>
          editingId === mapping.id ? (
            <MappingEditor
              key={mapping.id}
              orgId={orgId}
              connectionId={connectionId}
              existing={mapping}
              onSaved={() => {
                setEditingId(null);
                void load();
              }}
              onCancel={() => setEditingId(null)}
              onError={onError}
            />
          ) : (
            <div key={mapping.id} className="flex items-center justify-between rounded-lg bg-surface px-2.5 py-1.5">
              <span className="text-foreground-muted">
                {mapping.source_field} → {mapping.target_field}{mapping.transform ? ` (${mapping.transform})` : ""}
              </span>
              <div className="flex gap-2">
                <button type="button" onClick={() => setEditingId(mapping.id)} className="font-medium text-accent-hover hover:underline">Edit</button>
                <button type="button" onClick={() => void remove(mapping.id)} className="font-medium text-danger hover:underline">Delete</button>
              </div>
            </div>
          ),
        )}
        {mappings.length === 0 && <p className="text-foreground-muted">No mappings -- the raw payload is used as-is.</p>}
      </div>

      <div className="mt-3">
        <MappingEditor orgId={orgId} connectionId={connectionId} onSaved={() => void load()} onError={onError} />
      </div>
    </div>
  );
}
