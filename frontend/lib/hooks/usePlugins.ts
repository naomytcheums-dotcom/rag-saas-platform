"use client";

// Partie 16 (ter) -- marketplace listing hook, api/routers/plugins.py's
// own GET /marketplace/plugins (search/category/rating/sort filters).

import { useCallback, useEffect, useState } from "react";
import { ApiError } from "@/lib/api";
import { listPlugins, type PluginListFilters } from "@/lib/services/plugins";
import type { Plugin } from "@/lib/types";

export function usePlugins(filters: PluginListFilters) {
  const [plugins, setPlugins] = useState<Plugin[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  const key = JSON.stringify(filters);

  const load = useCallback(async () => {
    setLoading(true);
    setError(null);
    try {
      setPlugins(await listPlugins(filters));
    } catch (err) {
      setError(err instanceof ApiError ? String(err.detail) : "Failed to load the marketplace");
    } finally {
      setLoading(false);
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [key]);

  useEffect(() => {
    // eslint-disable-next-line react-hooks/set-state-in-effect
    void load();
  }, [load]);

  return { plugins, loading, error, reload: load };
}
