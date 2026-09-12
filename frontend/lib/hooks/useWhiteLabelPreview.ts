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
    void reload();
  }, [reload]);

  return { preview, loading, error, reload };
}
