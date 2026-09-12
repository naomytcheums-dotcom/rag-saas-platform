"use client";

import { ABTestChart } from "@/components/ab-tests/ABTestChart";
import { ABTestStatistics } from "@/components/ab-tests/ABTestStatistics";
import { useABTestResults } from "@/lib/hooks/useABTestResults";

interface ABTestResultsProps {
  testId: string;
}

export function ABTestResults({ testId }: ABTestResultsProps) {
  const { results, loading, error } = useABTestResults(testId);

  if (loading) return <p className="text-sm text-foreground-muted">Loading…</p>;
  if (error) return <p className="rounded-lg bg-danger-soft px-3 py-2 text-sm text-danger">{error}</p>;
  if (!results || Object.keys(results.metrics).length === 0) {
    return <p className="rounded-xl border border-border bg-surface p-5 text-sm text-foreground-muted">No metrics tracked yet.</p>;
  }

  return (
    <div className="flex flex-col gap-4">
      {Object.entries(results.metrics).map(([metric, result]) => (
        <div key={metric} className="flex flex-col gap-3">
          <ABTestStatistics metric={metric} result={result} />
          <ABTestChart label={metric} meanA={result.variant_a.mean} meanB={result.variant_b.mean} />
        </div>
      ))}
    </div>
  );
}
