"use client";

import { useRef, useState } from "react";
import { useMediaUpload } from "@/lib/hooks/useMediaUpload";
import type { MediaAsset } from "@/lib/services/media";

interface MediaUploadZoneProps {
  orgId: string;
  onUploaded: (asset: MediaAsset) => void;
}

export function MediaUploadZone({ orgId, onUploaded }: MediaUploadZoneProps) {
  const { upload, uploading, error } = useMediaUpload(orgId);
  const inputRef = useRef<HTMLInputElement>(null);
  const [dragging, setDragging] = useState(false);

  const handleFiles = async (files: FileList | null) => {
    if (!files || files.length === 0) return;
    const asset = await upload(files[0]);
    if (asset) onUploaded(asset);
  };

  return (
    <div
      onDragOver={(e) => { e.preventDefault(); setDragging(true); }}
      onDragLeave={() => setDragging(false)}
      onDrop={(e) => { e.preventDefault(); setDragging(false); void handleFiles(e.dataTransfer.files); }}
      onClick={() => inputRef.current?.click()}
      className={`flex cursor-pointer flex-col items-center justify-center rounded-xl border-2 border-dashed p-8 text-center transition-colors ${
        dragging ? "border-accent bg-accent-soft" : "border-border bg-surface hover:border-accent"
      }`}
    >
      <input ref={inputRef} type="file" accept="image/*,audio/*,video/*" className="hidden" onChange={(e) => void handleFiles(e.target.files)} />
      <p className="text-sm font-medium text-foreground">
        {uploading ? "Uploading…" : "Drop an image, audio, or video file here, or click to choose one"}
      </p>
      <p className="mt-1 text-xs text-foreground-muted">Images, audio, and video are processed automatically after upload.</p>
      {error && <p className="mt-2 text-xs text-danger">{error}</p>}
    </div>
  );
}
