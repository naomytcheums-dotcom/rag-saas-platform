"use client";

import { useEffect, useState } from "react";
import { fetchMediaFileBlobUrl } from "@/lib/services/media";

export function VideoPlayer({ mediaAssetId }: { mediaAssetId: string }) {
  const [url, setUrl] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    let objectUrl: string | null = null;
    fetchMediaFileBlobUrl(mediaAssetId)
      .then((u) => { objectUrl = u; setUrl(u); })
      .catch((err) => setError(err instanceof Error ? err.message : "Failed to load video"));
    return () => { if (objectUrl) URL.revokeObjectURL(objectUrl); };
  }, [mediaAssetId]);

  if (error) return <p className="text-xs text-danger">{error}</p>;
  if (!url) return <p className="text-xs text-foreground-muted">Loading video…</p>;
  return <video src={url} controls className="max-h-96 w-full rounded-lg bg-black" />;
}
