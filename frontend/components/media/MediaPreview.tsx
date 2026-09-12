"use client";

import { AudioPlayer } from "@/components/media/AudioPlayer";
import { ImagePreview } from "@/components/media/ImagePreview";
import { VideoPlayer } from "@/components/media/VideoPlayer";
import type { MediaAsset } from "@/lib/services/media";

export function MediaPreview({ asset }: { asset: MediaAsset }) {
  if (asset.media_type === "image") return <ImagePreview mediaAssetId={asset.id} />;
  if (asset.media_type === "audio") return <AudioPlayer mediaAssetId={asset.id} />;
  return <VideoPlayer mediaAssetId={asset.id} />;
}
