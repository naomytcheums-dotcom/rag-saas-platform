"use client";

import { useEffect, useState } from "react";
import { fetchMediaFileBlobUrl } from "@/lib/services/media";

export function ImagePreview({ mediaAssetId }: { mediaAssetId: string }) {
  const [url, setUrl] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    let objectUrl: string | null = null;
    fetchMediaFileBlobUrl(mediaAssetId)
      .then((u) => { objectUrl = u; setUrl(u); })
      .catch((err) => setError(err instanceof Error ? err.message : "Failed to load image"));
    return () => { if (objectUrl) URL.revokeObjectURL(objectUrl); };
  }, [mediaAssetId]);

  if (error) return <p className="text-xs text-danger">{error}</p>;
  if (!url) return <p className="text-xs text-foreground-muted">Loading image…</p>;
  // eslint-disable-next-line @next/next/no-img-element -- a real, private, blob: object URL, not a static/optimizable Next asset
  return <img src={url} alt="" className="max-h-96 w-full rounded-lg object-contain" />;
}
