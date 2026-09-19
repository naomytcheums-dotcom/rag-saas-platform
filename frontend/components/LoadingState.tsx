"use client";

import { useEffect, useState } from "react";

interface LoadingStateProps {
  /** Milliseconds before showing the "taking longer than expected"
   * fallback message. Default 6s -- long enough not to flash on a
   * normal load, short enough to reassure a real visitor waiting on a
   * slow cold-started backend (see docs/devops/MEMORY.md). */
  slowAfterMs?: number;
  onRetry?: () => void;
}

// Real gap found via audit (2026-09-19): every "Chargement…" state in
// this app was a plain, static label with no time limit and no way
// out if the backend was genuinely slow or stuck -- observed directly
// this session on a cold-started Render instance. This component is a
// drop-in replacement: same look while loading normally, a reassuring
// message plus an optional retry button once it's taken too long.
export default function LoadingState({ slowAfterMs = 6000, onRetry }: LoadingStateProps) {
  const [slow, setSlow] = useState(false);

  useEffect(() => {
    const timer = setTimeout(() => setSlow(true), slowAfterMs);
    return () => clearTimeout(timer);
  }, [slowAfterMs]);

  return (
    <div className="flex h-screen flex-col items-center justify-center gap-2 text-sm text-foreground-muted">
      <p>Chargement…</p>
      {slow && (
        <div className="flex flex-col items-center gap-2 text-center">
          <p>Ca prend plus de temps que prevu...</p>
          {onRetry && (
            <button
              type="button"
              onClick={onRetry}
              className="rounded-lg border border-border-strong px-3 py-1.5 text-sm text-foreground hover:bg-surface-muted"
            >
              Reessayer
            </button>
          )}
        </div>
      )}
    </div>
  );
}
