"use client";

import { useState } from "react";
import type { ABTest } from "@/lib/services/ab-tests";

interface ABTestDecisionProps {
  test: ABTest;
  onChooseWinner: (variant: "a" | "b") => Promise<unknown>;
  onDecide: () => Promise<unknown>;
}

export function ABTestDecision({ test, onChooseWinner, onDecide }: ABTestDecisionProps) {
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const runDecide = async () => {
    setBusy(true);
    setError(null);
    try {
      await onDecide();
    } catch (err) {
      setError(err instanceof Error ? err.message : "Could not decide automatically");
    } finally {
      setBusy(false);
    }
  };

  const runChoose = async (variant: "a" | "b") => {
    setBusy(true);
    setError(null);
    try {
      await onChooseWinner(variant);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Could not record the winner");
    } finally {
      setBusy(false);
    }
  };

  return (
    <div className="rounded-xl border border-border bg-surface p-5">
      <h2 className="text-xs font-medium uppercase text-foreground-muted">Decision</h2>
      {test.winner && test.winner !== "none" ? (
        <p className="mt-2 text-sm text-foreground">Automatic winner: <strong>Variant {test.winner.toUpperCase()}</strong></p>
      ) : (
        <div className="mt-3 flex flex-col gap-3">
          <button
            type="button" disabled={busy || !test.target_metric} onClick={() => void runDecide()}
            className="self-start rounded-lg bg-accent px-4 py-2 text-sm font-medium text-white hover:bg-accent-hover disabled:opacity-50"
          >
            Decide automatically
          </button>
          {!test.target_metric && <p className="text-xs text-foreground-muted">Set a target metric to enable automatic decisions.</p>}
          <div className="flex gap-2">
            <span className="text-xs text-foreground-muted self-center">Or choose manually:</span>
            <button type="button" disabled={busy} onClick={() => void runChoose("a")} className="rounded-lg border border-border px-3 py-1.5 text-xs font-medium text-foreground hover:bg-surface-muted">Variant A</button>
            <button type="button" disabled={busy} onClick={() => void runChoose("b")} className="rounded-lg border border-border px-3 py-1.5 text-xs font-medium text-foreground hover:bg-surface-muted">Variant B</button>
          </div>
        </div>
      )}
      {error && <p className="mt-2 text-xs text-danger">{error}</p>}
    </div>
  );
}
