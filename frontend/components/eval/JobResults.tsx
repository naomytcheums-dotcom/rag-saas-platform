"use client";

import { useEffect, useState } from "react";
import * as evalService from "@/lib/services/eval";
import type { EvalResult } from "@/lib/services/eval";

export function JobResults({ jobId }: { jobId: string }) {
  const [results, setResults] = useState<EvalResult[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    let cancelled = false;
    evalService.getJobResults(jobId).then((r) => {
      if (!cancelled) setResults(r.items);
    }).catch((err) => {
      if (!cancelled) setError(err instanceof Error ? err.message : "Failed to load results");
    }).finally(() => {
      if (!cancelled) setLoading(false);
    });
    return () => { cancelled = true; };
  }, [jobId]);

  if (loading) return <p className="text-sm text-foreground-muted">Loading results…</p>;
  if (error) return <p className="rounded-lg bg-danger-soft px-3 py-2 text-sm text-danger">{error}</p>;
  if (results.length === 0) return <p className="rounded-xl border border-border bg-surface p-5 text-sm text-foreground-muted">No successful results yet.</p>;

  return (
    <table className="w-full text-left text-sm">
      <thead>
        <tr className="text-xs text-foreground-muted">
          <th className="pb-2">Answer</th>
          <th className="pb-2">Recall@5</th>
          <th className="pb-2">Latency</th>
        </tr>
      </thead>
      <tbody>
        {results.map((r) => (
          <tr key={r.id} className="border-t border-border align-top">
            <td className="max-w-md py-2 pr-4 text-foreground">{r.actual_answer || <span className="text-foreground-muted">(empty — timed out)</span>}</td>
            <td className="py-2 pr-4 text-foreground-muted">{typeof r.metrics.recall_at_5 === "number" ? r.metrics.recall_at_5.toFixed(2) : "—"}</td>
            <td className="py-2 text-foreground-muted">{r.latency_ms} ms</td>
          </tr>
        ))}
      </tbody>
    </table>
  );
}
