"use client";

import { useState } from "react";
import Link from "next/link";
import * as mediaService from "@/lib/services/media";
import type { MediaSearchResult, MediaType } from "@/lib/services/media";

const TYPES: { label: string; value: MediaType | undefined }[] = [
  { label: "All", value: undefined }, { label: "Images", value: "image" }, { label: "Audio", value: "audio" }, { label: "Video", value: "video" },
];

export function MediaSearch() {
  const [query, setQuery] = useState("");
  const [mediaType, setMediaType] = useState<MediaType | undefined>(undefined);
  const [results, setResults] = useState<MediaSearchResult[]>([]);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const runSearch = async () => {
    if (!query.trim()) return;
    setLoading(true);
    setError(null);
    try {
      const response = await mediaService.searchMedia(query, mediaType);
      setResults(response.results);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Search failed");
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="flex flex-col gap-3">
      <div className="flex gap-2">
        <input
          value={query} onChange={(e) => setQuery(e.target.value)} onKeyDown={(e) => e.key === "Enter" && void runSearch()}
          placeholder="Search across images, audio, and video…"
          className="flex-1 rounded-lg border border-border bg-surface px-3 py-2 text-sm text-foreground"
        />
        <button type="button" onClick={() => void runSearch()} className="rounded-lg bg-accent px-4 py-2 text-sm font-medium text-white hover:bg-accent-hover">
          Search
        </button>
      </div>

      <div className="flex gap-2">
        {TYPES.map((t) => (
          <button
            key={t.label} type="button" onClick={() => setMediaType(t.value)}
            className={`rounded-full px-3 py-1 text-xs font-medium ${mediaType === t.value ? "bg-accent text-white" : "bg-surface-muted text-foreground-muted hover:bg-accent-soft"}`}
          >
            {t.label}
          </button>
        ))}
      </div>

      {loading && <p className="text-sm text-foreground-muted">Searching…</p>}
      {error && <p className="rounded-lg bg-danger-soft px-3 py-2 text-sm text-danger">{error}</p>}
      {!loading && results.length > 0 && (
        <div className="flex flex-col gap-2">
          {results.map((result) => (
            <Link
              key={`${result.media_asset_id}-${result.content.slice(0, 20)}`} href={`/dashboard/media/${result.media_asset_id}`}
              className="rounded-lg border border-border bg-surface p-3 hover:border-accent"
            >
              <div className="flex items-center justify-between">
                <span className="text-sm font-medium text-foreground">{result.filename}</span>
                <span className="text-xs text-foreground-muted">{(result.score * 100).toFixed(0)}% match</span>
              </div>
              <p className="mt-1 line-clamp-2 text-xs text-foreground-muted">{result.content}</p>
            </Link>
          ))}
        </div>
      )}
    </div>
  );
}
