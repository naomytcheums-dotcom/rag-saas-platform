"use client";

import { useState } from "react";
import { ABTestCard } from "@/components/ab-tests/ABTestCard";
import { ABTestFilters } from "@/components/ab-tests/ABTestFilters";
import { useABTests } from "@/lib/hooks/useABTests";

interface ABTestListProps {
  orgId: string;
}

export function ABTestList({ orgId }: ABTestListProps) {
  const { tests, loading, error } = useABTests(orgId);
  const [status, setStatus] = useState("all");

  if (loading) return <p className="text-sm text-foreground-muted">Loading…</p>;
  if (error) return <p className="rounded-lg bg-danger-soft px-3 py-2 text-sm text-danger">{error}</p>;

  const filtered = status === "all" ? tests : tests.filter((t) => t.status === status);

  return (
    <div className="flex flex-col gap-4">
      <div className="flex items-center justify-between">
        <ABTestFilters status={status} onStatusChange={setStatus} />
      </div>
      {filtered.length === 0 ? (
        <p className="rounded-xl border border-border bg-surface p-5 text-sm text-foreground-muted">No A/B tests yet.</p>
      ) : (
        <div className="grid grid-cols-1 gap-3 sm:grid-cols-2">
          {filtered.map((test) => <ABTestCard key={test.id} test={test} />)}
        </div>
      )}
    </div>
  );
}
