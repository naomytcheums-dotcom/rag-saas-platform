"use client";

// Real status polling (no fabricated progress bar -- this session's
// own standing "pas de barre de progression inutile" instruction):
// stops as soon as the real backend status is `completed`/`failed`.

import { useEffect, useState } from "react";
import * as mediaService from "@/lib/services/media";
import type { MediaAsset } from "@/lib/services/media";

const POLL_INTERVAL_MS = 2000;

export function useMediaProcessing(mediaAssetId: string | null) {
  const [asset, setAsset] = useState<MediaAsset | null>(null);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    if (!mediaAssetId) return;
    let cancelled = false;
    let timer: ReturnType<typeof setTimeout> | undefined;

    async function poll() {
      try {
        const current = await mediaService.getMediaStatus(mediaAssetId as string);
        if (cancelled) return;
        setAsset(current);
        if (current.status === "pending" || current.status === "processing") {
          timer = setTimeout(poll, POLL_INTERVAL_MS);
        }
      } catch (err) {
        if (!cancelled) setError(err instanceof Error ? err.message : "Failed to check status");
      }
    }

    void poll();
    return () => {
      cancelled = true;
      if (timer) clearTimeout(timer);
    };
  }, [mediaAssetId]);

  return { asset, error, isDone: asset?.status === "completed" || asset?.status === "failed" };
}
