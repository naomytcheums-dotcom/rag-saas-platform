"use client";

// Partie 16 (ter) -- one plugin's detail + real rating summary,
// api/routers/plugins.py's own GET /marketplace/plugins/{id} + /rating.

import { useCallback, useEffect, useState } from "react";
import { ApiError } from "@/lib/api";
import { getPlugin, getPluginRating } from "@/lib/services/plugins";
import type { Plugin, PluginRatingSummary } from "@/lib/types";

export function usePlugin(pluginId: string | undefined) {
  const [plugin, setPlugin] = useState<Plugin | null>(null);
  const [rating, setRating] = useState<PluginRatingSummary | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  const load = useCallback(async () => {
    if (!pluginId) return;
    setLoading(true);
    setError(null);
    try {
      const [pluginData, ratingData] = await Promise.all([getPlugin(pluginId), getPluginRating(pluginId)]);
      setPlugin(pluginData);
      setRating(ratingData);
    } catch (err) {
      setError(err instanceof ApiError ? String(err.detail) : "Failed to load this plugin");
    } finally {
      setLoading(false);
    }
  }, [pluginId]);

  useEffect(() => {
    // eslint-disable-next-line react-hooks/set-state-in-effect
    void load();
  }, [load]);

  return { plugin, rating, loading, error, reload: load };
}
