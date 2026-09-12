"use client";

import Link from "next/link";
import { ABTestStatusBadge } from "@/components/ab-tests/ABTestStatusBadge";
import type { ABTest } from "@/lib/services/ab-tests";

export function ABTestCard({ test }: { test: ABTest }) {
  return (
    <Link href={`/dashboard/ab-tests/${test.id}`} className="block rounded-xl border border-border bg-surface p-5 hover:border-accent">
      <div className="flex items-center justify-between">
        <h3 className="text-sm font-medium text-foreground">{test.name}</h3>
        <ABTestStatusBadge status={test.status} />
      </div>
      {test.description && <p className="mt-1 text-xs text-foreground-muted">{test.description}</p>}
      <div className="mt-3 flex gap-4 text-xs text-foreground-muted">
        <span>{test.traffic_split}% / {100 - test.traffic_split}%</span>
        {test.target_metric && <span>{test.target_metric}</span>}
        {test.winner && test.winner !== "none" && <span className="text-accent">Winner: {test.winner.toUpperCase()}</span>}
      </div>
    </Link>
  );
}
