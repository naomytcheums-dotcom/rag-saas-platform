"use client";

import { useState } from "react";
import { AgentCreateForm } from "@/components/autonomous/AgentCreateForm";
import { AgentList } from "@/components/autonomous/AgentList";
import { useCurrentOrg } from "@/lib/useCurrentOrg";

export default function Page() {
  const { org, loading } = useCurrentOrg();
  const [showForm, setShowForm] = useState(false);
  const [refreshKey, setRefreshKey] = useState(0);

  if (loading || !org) return <p className="mx-auto max-w-4xl text-sm text-foreground-muted">Loading…</p>;

  return (
    <div className="mx-auto max-w-4xl">
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-xl font-semibold text-foreground">Autonomous agents</h1>
          <p className="mt-1 text-sm text-foreground-muted">Agents that plan and execute toward a goal on their own.</p>
        </div>
        <button type="button" onClick={() => setShowForm((s) => !s)} className="rounded-lg bg-accent px-4 py-2 text-sm font-medium text-white hover:bg-accent-hover">
          {showForm ? "Cancel" : "New agent"}
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
