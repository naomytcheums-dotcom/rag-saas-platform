"use client";

import { useState } from "react";
import { api, ApiError } from "@/lib/api";
import ProviderList from "./ProviderList";
import type { UniversalConnection } from "@/lib/types";

interface ConnectionFormProps {
  orgId: string;
  onCreated: (connection: UniversalConnection) => void;
  onError: (message: string) => void;
}

// Partie 15.1 -- POST /organizations/{org_id}/integrations/connections.
export default function ConnectionForm({ orgId, onCreated, onError }: ConnectionFormProps) {
  const [name, setName] = useState("");
  const [provider, setProvider] = useState("webhook");
  const [action, setAction] = useState("log_only");
  const [submitting, setSubmitting] = useState(false);

  async function submit() {
    if (!name.trim()) return;
    setSubmitting(true);
    try {
      const created = await api.post<UniversalConnection>(`/organizations/${orgId}/integrations/connections`, { name, provider, action });
      setName("");
      onCreated(created);
    } catch (err) {
      onError(err instanceof ApiError ? String(err.detail) : "Failed to create connection");
    } finally {
      setSubmitting(false);
    }
  }

  return (
    <div className="rounded-xl border border-border bg-surface p-4">
      <h3 className="text-sm font-semibold text-foreground">New connection</h3>

      <div className="mt-2">
        <ProviderList selected={provider} onSelect={setProvider} />
      </div>

      <div className="mt-3 flex flex-wrap items-center gap-2">
        <input
          value={name}
          onChange={(e) => setName(e.target.value)}
          placeholder="Connection name"
          className="rounded-lg border border-border bg-background px-3 py-1.5 text-xs outline-none focus:border-accent"
        />
        <select value={action} onChange={(e) => setAction(e.target.value)} className="rounded-lg border border-border bg-background px-3 py-1.5 text-xs">
          <option value="log_only">Log only</option>
          <option value="ingest_document">Ingest as a document</option>
        </select>
        <button
          type="button"
          disabled={submitting || !name.trim()}
          onClick={() => void submit()}
          className="rounded-lg bg-accent px-3 py-1.5 text-xs font-medium text-white hover:bg-accent-hover disabled:opacity-50"
        >
          {submitting ? "Creating…" : "Create"}
        </button>
      </div>
    </div>
  );
}
