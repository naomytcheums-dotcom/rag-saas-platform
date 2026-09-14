"use client";

import { useRef, useState } from "react";
import { useFineTuningDatasets } from "@/lib/hooks/useFineTuningDatasets";

export function DatasetUpload({ orgId, onUploaded }: { orgId: string; onUploaded: () => void }) {
  const { upload } = useFineTuningDatasets(orgId);
  const [name, setName] = useState("");
  const [uploading, setUploading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const inputRef = useRef<HTMLInputElement>(null);

  const submit = async (file: File) => {
    if (!name.trim()) {
      setError("Give the dataset a name first.");
      return;
    }
    setUploading(true);
    setError(null);
    try {
      await upload({ name }, file);
      setName("");
      onUploaded();
    } catch (err) {
      setError(err instanceof Error ? err.message : "Upload failed");
    } finally {
      setUploading(false);
    }
  };

  return (
    <div className="flex flex-col gap-2 rounded-xl border border-border bg-surface p-4">
      <input value={name} onChange={(e) => setName(e.target.value)} placeholder="Dataset name" className="rounded-lg border border-border bg-background px-3 py-2 text-sm text-foreground" />
      <input ref={inputRef} type="file" accept=".jsonl" className="hidden" onChange={(e) => e.target.files?.[0] && void submit(e.target.files[0])} />
      <button
        type="button" onClick={() => inputRef.current?.click()} disabled={uploading}
        className="self-start rounded-lg bg-accent px-4 py-2 text-sm font-medium text-white hover:bg-accent-hover disabled:opacity-50"
      >
        {uploading ? "Uploading…" : "Upload .jsonl dataset"}
      </button>
      {error && <p className="text-xs text-danger">{error}</p>}
    </div>
  );
}
