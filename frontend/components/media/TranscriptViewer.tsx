"use client";

import { useEffect, useState } from "react";
import * as mediaService from "@/lib/services/media";
import type { MediaTranscript } from "@/lib/services/media";

export function TranscriptViewer({ mediaAssetId }: { mediaAssetId: string }) {
  const [transcript, setTranscript] = useState<MediaTranscript | null>(null);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    mediaService.getMediaTranscript(mediaAssetId)
      .then(setTranscript)
      .catch((err) => setError(err instanceof Error ? err.message : "No transcript available"));
  }, [mediaAssetId]);

  if (error) return <p className="text-xs text-foreground-muted">{error}</p>;
  if (!transcript) return <p className="text-xs text-foreground-muted">Loading transcript…</p>;

  return (
    <div className="rounded-lg border border-border bg-surface-muted p-3">
      <p className="whitespace-pre-wrap text-sm text-foreground">{transcript.text}</p>
      {transcript.provider && <p className="mt-2 text-xs text-foreground-muted">Transcribed via {transcript.provider}</p>}
    </div>
  );
}
