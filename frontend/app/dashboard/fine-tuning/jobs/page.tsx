"use client";

import { useState } from "react";
import { JobCreateForm } from "@/components/fine-tuning/JobCreateForm";
import { JobList } from "@/components/fine-tuning/JobList";
import { useCurrentOrg } from "@/lib/useCurrentOrg";

export default function Page() {
  const { org, loading } = useCurrentOrg();
  const [showForm, setShowForm] = useState(false);
  const [refreshKey, setRefreshKey] = useState(0);

  if (loading || !org) return <p className="mx-auto max-w-4xl text-sm text-foreground-muted">Loading…</p>;

  return (
    <div className="mx-auto max-w-4xl">
      <div className="flex items-center justify-between">
        <h1 className="text-xl font-semibold text-foreground">Fine-tuning jobs</h1>
        <button type="button" onClick={() => setShowForm((s) => !s)} className="rounded-lg bg-accent px-4 py-2 text-sm font-medium text-white hover:bg-accent-hover">
          {showForm ? "Cancel" : "New job"}
        </button>
      </div>

      {showForm && (
        <div className="mt-4">
          <JobCreateForm orgId={org.id} onCreated={() => { setShowForm(false); setRefreshKey((k) => k + 1); }} />
        </div>
      )}

      <div className="mt-5">
        <JobList key={refreshKey} orgId={org.id} />
      </div>
    </div>
  );
}
