"use client";

import { ABTestDecision } from "@/components/ab-tests/ABTestDecision";
import { ABTestResults } from "@/components/ab-tests/ABTestResults";
import { ABTestStatusBadge } from "@/components/ab-tests/ABTestStatusBadge";
import { exportABTestUrl } from "@/lib/services/ab-tests";
import { useABTest } from "@/lib/hooks/useABTest";

interface ABTestDetailProps {
  testId: string;
}

async function downloadExport(testId: string, format: "csv" | "json") {
  // A plain <a href> would send no Authorization header (this API uses
  // Bearer tokens, not cookies) -- same real fix as
  // components/analytics/ExportButton.tsx's own docstring.
  const token = window.localStorage.getItem("access_token");
  const response = await fetch(exportABTestUrl(testId, format), {
    headers: token ? { Authorization: `Bearer ${token}` } : undefined,
    credentials: "include",
  });
  if (!response.ok) return;
  const blob = await response.blob();
  const url = URL.createObjectURL(blob);
  const a = document.createElement("a");
  a.href = url;
  a.download = `ab_test.${format}`;
  a.click();
  URL.revokeObjectURL(url);
}

export function ABTestDetail({ testId }: ABTestDetailProps) {
  const { test, loading, error, start, pause, resume, complete, chooseWinner, decide } = useABTest(testId);

  if (loading) return <p className="mx-auto max-w-3xl text-sm text-foreground-muted">Loading…</p>;
  if (error) return <p className="mx-auto max-w-3xl rounded-lg bg-danger-soft px-3 py-2 text-sm text-danger">{error}</p>;
  if (!test) return null;

  return (
    <div className="mx-auto max-w-3xl">
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-xl font-semibold text-foreground">{test.name}</h1>
          {test.description && <p className="mt-1 text-sm text-foreground-muted">{test.description}</p>}
        </div>
        <ABTestStatusBadge status={test.status} />
      </div>

      <div className="mt-4 flex flex-wrap gap-2">
        {test.status === "draft" && (
          <button type="button" onClick={() => void start()} className="rounded-lg bg-accent px-3 py-1.5 text-sm font-medium text-white hover:bg-accent-hover">Start</button>
        )}
        {test.status === "running" && (
          <button type="button" onClick={() => void pause()} className="rounded-lg border border-border px-3 py-1.5 text-sm font-medium text-foreground hover:bg-surface-muted">Pause</button>
        )}
        {test.status === "paused" && (
          <button type="button" onClick={() => void resume()} className="rounded-lg bg-accent px-3 py-1.5 text-sm font-medium text-white hover:bg-accent-hover">Resume</button>
        )}
        {(test.status === "running" || test.status === "paused") && (
          <button type="button" onClick={() => void complete()} className="rounded-lg border border-border px-3 py-1.5 text-sm font-medium text-foreground hover:bg-surface-muted">Complete</button>
        )}
        <button type="button" onClick={() => void downloadExport(test.id, "csv")} className="rounded-lg border border-border px-3 py-1.5 text-sm font-medium text-foreground hover:bg-surface-muted">Export CSV</button>
        <button type="button" onClick={() => void downloadExport(test.id, "json")} className="rounded-lg border border-border px-3 py-1.5 text-sm font-medium text-foreground hover:bg-surface-muted">Export JSON</button>
      </div>

      <div className="mt-5">
        <ABTestDecision test={test} onChooseWinner={chooseWinner} onDecide={decide} />
      </div>

      <h2 className="mt-6 text-sm font-medium text-foreground">Results</h2>
      <div className="mt-3">
        <ABTestResults testId={test.id} />
      </div>
    </div>
  );
}
