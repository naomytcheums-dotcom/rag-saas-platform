"use client";

// Partie 16 (ter) -- this org's installed plugins,
// api/routers/plugins.py's own GET /organizations/{org_id}/plugins/installed.

import { useCallback, useEffect, useState } from "react";
import { ApiError } from "@/lib/api";
import { listInstalledPlugins } from "@/lib/services/plugins";
import type { PluginInstallation } from "@/lib/types";

export function useInstalledPlugins(orgId: string | undefined) {
  const [installations, setInstallations] = useState<PluginInstallation[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  const load = useCallback(async () => {
    if (!orgId) return;
    setLoading(true);
    setError(null);
    try {
      setInstallations(await listInstalledPlugins(orgId));
    } catch (err) {
      setError(err instanceof ApiError ? String(err.detail) : "Failed to load installed plugins");
    } finally {
      setLoading(false);
    }
  }, [orgId]);

  useEffect(() => {
    // eslint-disable-next-line react-hooks/set-state-in-effect
    void load();
  }, [load]);

  return { installations, loading, error, reload: load };
}
