"use client";

import { useCallback, useState } from "react";
import * as mediaService from "@/lib/services/media";
import type { MediaAsset } from "@/lib/services/media";

export function useMediaUpload(orgId: string) {
  const [uploading, setUploading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const upload = useCallback(async (file: File): Promise<MediaAsset | null> => {
    setUploading(true);
    setError(null);
    try {
      return await mediaService.uploadMedia(orgId, file);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Upload failed");
      return null;
    } finally {
      setUploading(false);
    }
  }, [orgId]);

  return { upload, uploading, error };
}
