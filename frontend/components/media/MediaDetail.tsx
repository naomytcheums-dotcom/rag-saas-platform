"use client";

import { useEffect, useState } from "react";
import { DescriptionViewer } from "@/components/media/DescriptionViewer";
import { FrameGallery } from "@/components/media/FrameGallery";
import { MediaPreview } from "@/components/media/MediaPreview";
import { MediaStatusBadge } from "@/components/media/MediaStatusBadge";
import { TranscriptViewer } from "@/components/media/TranscriptViewer";
import { useMediaProcessing } from "@/lib/hooks/useMediaProcessing";
import * as mediaService from "@/lib/services/media";
import type { MediaAsset } from "@/lib/services/media";

export function MediaDetail({ mediaAssetId }: { mediaAssetId: string }) {
  const [asset, setAsset] = useState<MediaAsset | null>(null);
  const [error, setError] = useState<string | null>(null);
  const stillProcessing = asset?.status === "pending" || asset?.status === "processing";
  const { asset: polled } = useMediaProcessing(stillProcessing ? mediaAssetId : null);

  useEffect(() => {
    mediaService.getMedia(mediaAssetId).then(setAsset).catch((err) => setError(err instanceof Error ? err.message : "Not found"));
  }, [mediaAssetId]);

  useEffect(() => {
    // eslint-disable-next-line react-hooks/set-state-in-effect -- justified: syncing with a real external system (the backend API) after mount/param change, not a value derivable from props/state.
    if (polled) setAsset(polled);
  }, [polled]);

  if (error) return <p className="rounded-lg bg-danger-soft px-3 py-2 text-sm text-danger">{error}</p>;
  if (!asset) return <p className="text-sm text-foreground-muted">Loading…</p>;

  return (
    <div className="flex flex-col gap-5">
      <div className="flex items-center justify-between">
        <h1 className="text-lg font-semibold text-foreground">{asset.filename}</h1>
        <MediaStatusBadge status={asset.status} />
      </div>

      {asset.status === "failed" && asset.error && (
        <p className="rounded-lg bg-danger-soft px-3 py-2 text-sm text-danger">{asset.error}</p>
      )}
      {stillProcessing && <p className="text-sm text-foreground-muted">Processing… this page updates automatically.</p>}

      <MediaPreview asset={asset} />

      <section>
        <h2 className="text-sm font-semibold text-foreground">Description</h2>
        <div className="mt-2"><DescriptionViewer asset={asset} /></div>
      </section>

      {(asset.media_type === "audio" || asset.media_type === "video") && asset.status === "completed" && (
        <section>
          <h2 className="text-sm font-semibold text-foreground">Transcript</h2>
          <div className="mt-2"><TranscriptViewer mediaAssetId={asset.id} /></div>
        </section>
      )}

      {asset.media_type === "video" && asset.status === "completed" && (
        <section>
          <h2 className="text-sm font-semibold text-foreground">Extracted frames</h2>
          <div className="mt-2"><FrameGallery mediaAssetId={asset.id} /></div>
        </section>
      )}
    </div>
  );
}
