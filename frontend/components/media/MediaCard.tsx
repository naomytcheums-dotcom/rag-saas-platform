"use client";

import Link from "next/link";
import { MediaStatusBadge } from "@/components/media/MediaStatusBadge";
import type { MediaAsset } from "@/lib/services/media";

const TYPE_ICON: Record<string, string> = { image: "🖼", audio: "🎵", video: "🎬" };

export function MediaCard({ asset }: { asset: MediaAsset }) {
  return (
    <Link href={`/dashboard/media/${asset.id}`} className="block rounded-xl border border-border bg-surface p-4 hover:border-accent">
      <div className="flex items-center justify-between">
        <span className="text-sm font-medium text-foreground">{TYPE_ICON[asset.media_type] ?? ""} {asset.filename}</span>
        <MediaStatusBadge status={asset.status} />
      </div>
      {asset.description && <p className="mt-2 line-clamp-2 text-xs text-foreground-muted">{asset.description}</p>}
      <div className="mt-3 flex gap-3 text-xs text-foreground-muted">
        <span>{(asset.file_size / 1024).toFixed(0)} KB</span>
        {asset.duration_ms != null && <span>{Math.round(asset.duration_ms / 1000)}s</span>}
      </div>
    </Link>
  );
}
