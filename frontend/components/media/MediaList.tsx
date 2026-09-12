"use client";

import { useState } from "react";
import { MediaCard } from "@/components/media/MediaCard";
import { useMedia } from "@/lib/hooks/useMedia";
import type { MediaType } from "@/lib/services/media";

const FILTERS: { label: string; value: MediaType | "all" }[] = [
  { label: "All", value: "all" }, { label: "Images", value: "image" }, { label: "Audio", value: "audio" }, { label: "Video", value: "video" },
];

export function MediaList({ orgId }: { orgId: string }) {
  const [filter, setFilter] = useState<MediaType | "all">("all");
  const { items, loading, error } = useMedia(orgId, filter === "all" ? undefined : filter);

  return (
    <div className="flex flex-col gap-4">
      <div className="flex gap-2">
        {FILTERS.map((f) => (
          <button
            key={f.value} type="button" onClick={() => setFilter(f.value)}
            className={`rounded-full px-3 py-1 text-xs font-medium ${filter === f.value ? "bg-accent text-white" : "bg-surface-muted text-foreground-muted hover:bg-accent-soft"}`}
          >
            {f.label}
          </button>
        ))}
      </div>

      {loading && <p className="text-sm text-foreground-muted">Loading…</p>}
      {error && <p className="rounded-lg bg-danger-soft px-3 py-2 text-sm text-danger">{error}</p>}
      {!loading && !error && items.length === 0 && (
        <p className="rounded-xl border border-border bg-surface p-5 text-sm text-foreground-muted">No media yet.</p>
      )}
      {!loading && items.length > 0 && (
        <div className="grid grid-cols-1 gap-3 sm:grid-cols-2 lg:grid-cols-3">
          {items.map((asset) => <MediaCard key={asset.id} asset={asset} />)}
        </div>
      )}
    </div>
  );
}
