"use client";

import LoadingState from "@/components/LoadingState";
import { useState } from "react";
import { AgentCreateForm } from "@/components/autonomous/AgentCreateForm";
import { AgentList } from "@/components/autonomous/AgentList";
import { useCurrentOrg } from "@/lib/useCurrentOrg";

export default function Page() {
  const { org, loading } = useCurrentOrg();
  const [showForm, setShowForm] = useState(false);
  const [refreshKey, setRefreshKey] = useState(0);

  if (loading || !org) return <LoadingState fullScreen={false} />;

  return (
    <div className="mx-auto max-w-4xl">
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-xl font-semibold text-foreground">Agents autonomes</h1>
          <p className="mt-1 text-sm text-foreground-muted">Des agents qui planifient et exécutent un objectif de façon autonome.</p>
        </div>
        <button type="button" onClick={() => setShowForm((s) => !s)} className="rounded-lg bg-accent px-4 py-2 text-sm font-medium text-white hover:bg-accent-hover">
          {showForm ? "Annuler" : "Nouvel agent"}
        </button>
      </div>

      {showForm && (
        <div className="mt-4">
          <AgentCreateForm orgId={org.id} onCreated={() => { setShowForm(false); setRefreshKey((k) => k + 1); }} />
        </div>
      )}

      <div className="mt-5">
        <AgentList key={refreshKey} orgId={org.id} />
      </div>
    </div>
  );
}
