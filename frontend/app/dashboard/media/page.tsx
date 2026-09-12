"use client";

import { useState } from "react";
import { MediaList } from "@/components/media/MediaList";
import { MediaSearch } from "@/components/media/MediaSearch";
import { MediaUploadZone } from "@/components/media/MediaUploadZone";
import { useCurrentOrg } from "@/lib/useCurrentOrg";

export default function Page() {
  const { org, loading } = useCurrentOrg();
  const [tab, setTab] = useState<"library" | "search">("library");
  const [refreshKey, setRefreshKey] = useState(0);

  if (loading || !org) return <p className="mx-auto max-w-4xl text-sm text-foreground-muted">Loading…</p>;

  return (
    <div className="mx-auto max-w-4xl">
      <h1 className="text-xl font-semibold text-foreground">Media</h1>
      <p className="mt-1 text-sm text-foreground-muted">Upload images, audio, and video — each is automatically processed and made searchable.</p>

      <div className="mt-4">
        <MediaUploadZone orgId={org.id} onUploaded={() => setRefreshKey((k) => k + 1)} />
      </div>

      <div className="mt-6 flex gap-2 border-b border-border">
        <button
          type="button" onClick={() => setTab("library")}
          className={`border-b-2 px-3 py-2 text-sm font-medium ${tab === "library" ? "border-accent text-accent" : "border-transparent text-foreground-muted"}`}
        >
          Library
        </button>
        <button
          type="button" onClick={() => setTab("search")}
          className={`border-b-2 px-3 py-2 text-sm font-medium ${tab === "search" ? "border-accent text-accent" : "border-transparent text-foreground-muted"}`}
        >
          Search
        </button>
      </div>

      <div className="mt-5">
        {tab === "library" ? <MediaList key={refreshKey} orgId={org.id} /> : <MediaSearch />}
      </div>
    </div>
  );
}
