"use client";

import { useRef, useState } from "react";

interface LogoUploadProps {
  logoUrl: string | null;
  onUpload: (file: File) => Promise<unknown>;
  onRemove: () => Promise<unknown>;
}

export function LogoUpload({ logoUrl, onUpload, onRemove }: LogoUploadProps) {
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

  const handleRemove = async () => {
    setBusy(true);
    try {
      await onRemove();
    } finally {
      setBusy(false);
    }
  };

  return (
    <div className="rounded-xl border border-border bg-surface p-5">
      <h2 className="text-xs font-medium uppercase text-foreground-muted">Logo</h2>
      <div className="mt-3 flex items-center gap-4">
        <div className="flex h-16 w-16 items-center justify-center overflow-hidden rounded-lg border border-border bg-surface-muted">
          {logoUrl ? (
            // eslint-disable-next-line @next/next/no-img-element
            <img src={logoUrl} alt="Logo" className="max-h-full max-w-full object-contain" />
          ) : (
            <span className="text-[10px] text-foreground-muted">No logo</span>
          )}
        </div>
        <div className="flex flex-col gap-2">
          <div className="flex gap-2">
            <button
              type="button" disabled={busy} onClick={() => inputRef.current?.click()}
              className="rounded-lg bg-accent px-3 py-1.5 text-xs font-medium text-white hover:bg-accent-hover disabled:opacity-50"
            >
              {logoUrl ? "Replace" : "Upload"}
            </button>
            {logoUrl && (
              <button type="button" disabled={busy} onClick={() => void handleRemove()} className="rounded-lg border border-border px-3 py-1.5 text-xs font-medium text-foreground-muted hover:text-danger">
                Remove
              </button>
            )}
          </div>
          <p className="text-xs text-foreground-muted">PNG or JPG, up to 2 MB.</p>
        </div>
      </div>
      <input
        ref={inputRef} type="file" accept="image/png,image/jpeg,image/svg+xml" className="hidden"
        onChange={(e) => { const file = e.target.files?.[0]; if (file) void handleFile(file); e.target.value = ""; }}
      />
      {error && <p className="mt-2 text-xs text-danger">{error}</p>}
    </div>
  );
}
