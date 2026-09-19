"use client";

import { useCallback, useEffect, useState } from "react";
import { getPreview } from "@/lib/services/whitelabel";
import type { WhiteLabelConfig } from "@/lib/services/whitelabel";

export function useWhiteLabelPreview(orgId: string) {
  const [preview, setPreview] = useState<WhiteLabelConfig | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  const reload = useCallback(async () => {
    setLoading(true);
    try {
      setPreview(await getPreview(orgId));
      setError(null);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Failed to load preview");
    } finally {
      setLoading(false);
    }
  }, [orgId]);

  useEffect(() => {
    // eslint-disable-next-line react-hooks/set-state-in-effect -- justified: syncing with a real external system (the backend API) after mount/param change, not a value derivable from props/state.
    void reload();
  }, [reload]);

  return { preview, loading, error, reload };
}
