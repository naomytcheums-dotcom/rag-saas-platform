"use client";

import { useEffect, useState } from "react";
import * as evalService from "@/lib/services/eval";
import type { EvalFailure, EvalFailureCategories } from "@/lib/services/eval";

const CATEGORY_LABEL: Record<string, string> = {
  retrieval: "Retrieval failure",
  generation: "Generation failure",
  other: "Other error",
  hallucination: "Suspected hallucination",
};

export function FailureAnalysis({ jobId }: { jobId: string }) {
  const [categories, setCategories] = useState<EvalFailureCategories | null>(null);
  const [failures, setFailures] = useState<EvalFailure[]>([]);
  const [filter, setFilter] = useState<string>("all");
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    let cancelled = false;
    Promise.all([evalService.getJobFailureCategories(jobId), evalService.getJobFailures(jobId)])
      .then(([cats, fails]) => {
        if (cancelled) return;
        setCategories(cats);
        setFailures(fails.items);
      })
      .catch((err) => { if (!cancelled) setError(err instanceof Error ? err.message : "Failed to load failure analysis"); })
      .finally(() => { if (!cancelled) setLoading(false); });
    return () => { cancelled = true; };
  }, [jobId]);

  if (loading) return <p className="text-sm text-foreground-muted">Loading failure analysis…</p>;
  if (error) return <p className="rounded-lg bg-danger-soft px-3 py-2 text-sm text-danger">{error}</p>;
  if (!categories) return null;

  const totalFailures = categories.retrieval + categories.generation + categories.other;
  const filtered = filter === "all" ? failures : failures.filter((f) => f.category === filter);

  return (
    <div className="flex flex-col gap-4">
      <div className="grid grid-cols-2 gap-3 sm:grid-cols-4">
        {(["retrieval", "generation", "other", "hallucination"] as const).map((cat) => (
          <button
            key={cat} type="button" onClick={() => setFilter(filter === cat ? "all" : cat)}
            className={`rounded-xl border p-4 text-left ${filter === cat ? "border-accent bg-accent-soft" : "border-border bg-surface"}`}
          >
            <p className="text-xs text-foreground-muted">{CATEGORY_LABEL[cat]}</p>
            <p className="mt-1 text-lg font-semibold text-foreground">{categories[cat]}</p>
          </button>
        ))}
      </div>

      {totalFailures === 0 ? (
        <p className="rounded-xl border border-border bg-surface p-5 text-sm text-foreground-muted">No exceptions recorded for this run — questions that answered but scored a high hallucination rate are shown in the "Suspected hallucination" card above, not listed below (they have no exception to display).</p>
      ) : filtered.length === 0 ? (
        <p className="text-sm text-foreground-muted">No failures in this category.</p>
      ) : (
        <div className="flex flex-col gap-2">
          {filtered.map((f) => (
            <div key={f.id} className="rounded-xl border border-border bg-surface p-3">
              <p className="text-xs font-medium text-danger">{CATEGORY_LABEL[f.category] ?? f.category}</p>
              <p className="mt-1 text-sm text-foreground-muted">{f.error}</p>
            </div>
          ))}
        </div>
      )}
    </div>
  );
}
