"use client";

// Partie 22, 3rd finalization -- real CLIP-based visual search:
// text-to-image and image-to-image, genuinely distinct from
// MediaSearch.tsx's own text search over LLM-written descriptions
// (this compares a query directly against real image content).

import { useRef, useState } from "react";
import Link from "next/link";
import * as mediaService from "@/lib/services/media";
import type { VisualSearchResult } from "@/lib/services/media";

export function VisualSearch() {
  const [query, setQuery] = useState("");
  const [results, setResults] = useState<VisualSearchResult[]>([]);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const inputRef = useRef<HTMLInputElement>(null);

  const runTextSearch = async () => {
    if (!query.trim()) return;
    setLoading(true);
    setError(null);
    try {
      const response = await mediaService.searchVisual(query);
      setResults(response.results);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Search failed");
    } finally {
      setLoading(false);
    }
  };

  const runImageSearch = async (file: File) => {
    setLoading(true);
    setError(null);
    try {
      const response = await mediaService.searchSimilar(file);
      setResults(response.results);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Search failed");
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="flex flex-col gap-3">
      <p className="text-xs text-foreground-muted">Searches real image content directly (CLIP), not written descriptions.</p>

      <div className="flex gap-2">
        <input
          value={query} onChange={(e) => setQuery(e.target.value)} onKeyDown={(e) => e.key === "Enter" && void runTextSearch()}
          placeholder="Describe what the image should show…"
          className="flex-1 rounded-lg border border-border bg-surface px-3 py-2 text-sm text-foreground"
        />
        <button type="button" onClick={() => void runTextSearch()} className="rounded-lg bg-accent px-4 py-2 text-sm font-medium text-white hover:bg-accent-hover">
          Search
        </button>
      </div>

      <div className="flex items-center gap-2">
        <span className="text-xs text-foreground-muted">or find images similar to:</span>
        <input
          ref={inputRef} type="file" accept="image/*" className="hidden"
          onChange={(e) => e.target.files?.[0] && void runImageSearch(e.target.files[0])}
        />
        <button type="button" onClick={() => inputRef.current?.click()} className="rounded-lg border border-border px-3 py-1.5 text-xs font-medium text-foreground hover:bg-surface-muted">
          Upload an image
        </button>
      </div>

      {loading && <p className="text-sm text-foreground-muted">Searching…</p>}
      {error && <p className="rounded-lg bg-danger-soft px-3 py-2 text-sm text-danger">{error}</p>}
      {!loading && results.length > 0 && (
        <div className="grid grid-cols-2 gap-2 sm:grid-cols-3">
          {results.map((result) => (
            <Link
              key={result.media_asset_id} href={`/dashboard/media/${result.media_asset_id}`}
              className="rounded-lg border border-border bg-surface p-3 hover:border-accent"
            >
              <p className="truncate text-sm font-medium text-foreground">{result.filename}</p>
              <p className="text-xs text-foreground-muted">{(result.score * 100).toFixed(0)}% similar</p>
            </Link>
          ))}
        </div>
      )}
    </div>
  );
}
