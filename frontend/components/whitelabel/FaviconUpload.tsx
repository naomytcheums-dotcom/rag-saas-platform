"use client";

import { useRef, useState } from "react";

interface FaviconUploadProps {
  faviconUrl: string | null;
  onUpload: (file: File) => Promise<unknown>;
}

export function FaviconUpload({ faviconUrl, onUpload }: FaviconUploadProps) {
  const inputRef = useRef<HTMLInputElement>(null);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const handleFile = async (file: File) => {
    setBusy(true);
    setError(null);
    try {
      await onUpload(file);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Upload failed");
    } finally {
      setBusy(false);
    }
  };

  return (
    <div className="rounded-xl border border-border bg-surface p-5">
      <h2 className="text-xs font-medium uppercase text-foreground-muted">Favicon</h2>
      <div className="mt-3 flex items-center gap-4">
        <div className="flex h-8 w-8 items-center justify-center overflow-hidden rounded border border-border bg-surface-muted">
          {faviconUrl ? (
            // eslint-disable-next-line @next/next/no-img-element
            <img src={faviconUrl} alt="Favicon" className="max-h-full max-w-full object-contain" />
          ) : (
            <span className="text-[8px] text-foreground-muted">—</span>
          )}
        </div>
        <button
          type="button" disabled={busy} onClick={() => inputRef.current?.click()}
          className="rounded-lg bg-accent px-3 py-1.5 text-xs font-medium text-white hover:bg-accent-hover disabled:opacity-50"
        >
          {faviconUrl ? "Replace" : "Upload"}
        </button>
      </div>
      <input
        ref={inputRef} type="file" accept="image/x-icon,image/png" className="hidden"
        onChange={(e) => { const file = e.target.files?.[0]; if (file) void handleFile(file); e.target.value = ""; }}
      />
      {error && <p className="mt-2 text-xs text-danger">{error}</p>}
    </div>
  );
}
