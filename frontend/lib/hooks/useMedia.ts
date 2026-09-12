"use client";

import { useCallback, useEffect, useState } from "react";
import * as mediaService from "@/lib/services/media";
import type { MediaAsset, MediaType } from "@/lib/services/media";

export function useMedia(orgId: string, mediaType?: MediaType) {
  const [items, setItems] = useState<MediaAsset[]>([]);
  const [total, setTotal] = useState(0);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  const reload = useCallback(async () => {
    setLoading(true);
    try {
      const response = await mediaService.listMedia(orgId, mediaType);
      setItems(response.items);
      setTotal(response.total);
      setError(null);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Failed to load media");
    } finally {
      setLoading(false);
    }
  }, [orgId, mediaType]);

  useEffect(() => {
    void reload();
  }, [reload]);

  const remove = useCallback(async (id: string) => {
    await mediaService.deleteMedia(id);
    await reload();
  }, [reload]);

  return { items, total, loading, error, reload, remove };
}
