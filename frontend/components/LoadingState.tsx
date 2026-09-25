"use client";

import { useEffect, useState } from "react";
import { useTranslation } from "@/lib/i18n";

interface LoadingStateProps {
  /** Milliseconds before showing the "taking longer than expected"
   * fallback message. Default 6s -- long enough not to flash on a
   * normal load, short enough to reassure a real visitor waiting on a
   * slow cold-started backend (see docs/devops/MEMORY.md). */
  slowAfterMs?: number;
  onRetry?: () => void;
  /** true (default) centers in the full viewport height -- for a page
   * with no other chrome rendered yet (root layout gate, route
   * `loading.tsx`). false renders inline instead, for a loading state
   * nested inside an already-rendered layout (e.g. a dashboard page
   * whose sidebar/header are already on screen). */
  fullScreen?: boolean;
}

export default function LoadingState({ slowAfterMs = 6000, onRetry, fullScreen = true }: LoadingStateProps) {
  const { t } = useTranslation();
  const [slow, setSlow] = useState(false);

  useEffect(() => {
    const timer = setTimeout(() => setSlow(true), slowAfterMs);
    return () => clearTimeout(timer);
  }, [slowAfterMs]);

  return (
    <div className={`flex flex-col items-center justify-center gap-2 text-sm text-foreground-muted ${fullScreen ? "h-screen" : "py-10"}`}>
      <p>{t("loading.label")}</p>
      {slow && (
        <div className="flex flex-col items-center gap-2 text-center">
          <p>{t("loading.slow")}</p>
          {onRetry && (
            <button
              type="button"
              onClick={onRetry}
              className="rounded-lg border border-border-strong px-3 py-1.5 text-sm text-foreground hover:bg-surface-muted"
            >
              {t("loading.retry")}
            </button>
          )}
        </div>
      )}
    </div>
  );
}
