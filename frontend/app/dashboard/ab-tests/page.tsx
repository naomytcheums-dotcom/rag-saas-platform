"use client";

import { useState } from "react";
import { ABTestCreateForm } from "@/components/ab-tests/ABTestCreateForm";
import { ABTestList } from "@/components/ab-tests/ABTestList";
import { useCurrentOrg } from "@/lib/useCurrentOrg";

export default function Page() {
  const { org, loading } = useCurrentOrg();
  const [showForm, setShowForm] = useState(false);

  if (loading || !org) return <p className="mx-auto max-w-4xl text-sm text-foreground-muted">Loading…</p>;

  return (
    <div className="mx-auto max-w-4xl">
      <div className="flex items-center justify-between">
        <h1 className="text-xl font-semibold text-foreground">A/B tests</h1>
        <button type="button" onClick={() => setShowForm((s) => !s)} className="rounded-lg bg-accent px-4 py-2 text-sm font-medium text-white hover:bg-accent-hover">
          {showForm ? "Cancel" : "New test"}
        </button>
      </div>

      {showForm && (
        <div className="mt-4">
          <ABTestCreateForm orgId={org.id} onCreated={() => setShowForm(false)} />
        </div>
      )}

      <div className="mt-5">
        <ABTestList orgId={org.id} />
      </div>
    </div>
  );
}
