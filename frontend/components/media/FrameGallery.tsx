"use client";

import { useEffect, useState } from "react";
import * as mediaService from "@/lib/services/media";
import { fetchMediaFrameFileBlobUrl } from "@/lib/services/media";
import type { MediaFrame } from "@/lib/services/media";

function FrameThumbnail({ mediaAssetId, frame }: { mediaAssetId: string; frame: MediaFrame }) {
  const [url, setUrl] = useState<string | null>(null);

  useEffect(() => {
    let objectUrl: string | null = null;
    fetchMediaFrameFileBlobUrl(mediaAssetId, frame.id).then((u) => { objectUrl = u; setUrl(u); }).catch(() => setUrl(null));
    return () => { if (objectUrl) URL.revokeObjectURL(objectUrl); };
  }, [mediaAssetId, frame.id]);

  return (
    <div className="rounded-lg border border-border bg-surface p-2">
      {/* eslint-disable-next-line @next/next/no-img-element -- a real, private, blob: object URL */}
      {url && <img src={url} alt="" className="h-32 w-full rounded object-cover" />}
      <p className="mt-1 text-xs text-foreground-muted">{(frame.timestamp_ms / 1000).toFixed(1)}s</p>
      {frame.description && <p className="line-clamp-2 text-xs text-foreground">{frame.description}</p>}
    </div>
  );
}

export function FrameGallery({ mediaAssetId }: { mediaAssetId: string }) {
  const [frames, setFrames] = useState<MediaFrame[]>([]);

  useEffect(() => {
    mediaService.listMediaFrames(mediaAssetId).then(setFrames).catch(() => setFrames([]));
  }, [mediaAssetId]);

  if (frames.length === 0) return <p className="text-xs text-foreground-muted">No frames extracted yet.</p>;

  return (
    <div className="grid grid-cols-2 gap-2 sm:grid-cols-4">
      {frames.map((frame) => <FrameThumbnail key={frame.id} mediaAssetId={mediaAssetId} frame={frame} />)}
    </div>
  );
}
