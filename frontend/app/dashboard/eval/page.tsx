"use client";

import { useState } from "react";
import { DatasetForm } from "@/components/eval/DatasetForm";
import { DatasetList } from "@/components/eval/DatasetList";
import { useCurrentOrg } from "@/lib/useCurrentOrg";

export default function Page() {
  const { org, loading } = useCurrentOrg();
  const [showForm, setShowForm] = useState(false);
  const [listVersion, setListVersion] = useState(0);

  if (loading || !org) return <p className="mx-auto max-w-4xl text-sm text-foreground-muted">Loading…</p>;

  return (
    <div className="mx-auto max-w-4xl">
      <div className="flex items-center justify-between">
        <h1 className="text-xl font-semibold text-foreground">Eval Lab</h1>
        <button type="button" onClick={() => setShowForm((s) => !s)} className="rounded-lg bg-accent px-4 py-2 text-sm font-medium text-white hover:bg-accent-hover">
          {showForm ? "Cancel" : "New dataset"}
        </button>
      </div>

      {showForm && (
        <div className="mt-4">
          <DatasetForm orgId={org.id} onCreated={() => { setShowForm(false); setListVersion((v) => v + 1); }} />
        </div>
      )}

      <div className="mt-5">
        <DatasetList key={listVersion} orgId={org.id} />
      </div>
    </div>
  );
}
