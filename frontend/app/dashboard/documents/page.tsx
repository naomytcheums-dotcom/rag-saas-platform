"use client";

import { useCallback, useEffect, useState } from "react";
import { api, ApiError } from "@/lib/api";
import { useCurrentOrg } from "@/lib/useCurrentOrg";

interface DocumentEntry {
  id: string;
  name: string;
  file_size: number;
  file_type: string;
  status: string;
}

function formatSize(bytes: number): string {
  if (bytes < 1024) return `${bytes} B`;
  if (bytes < 1024 * 1024) return `${(bytes / 1024).toFixed(1)} KB`;
  return `${(bytes / (1024 * 1024)).toFixed(1)} MB`;
}

export default function DocumentsPage() {
  const { org } = useCurrentOrg();
  const [documents, setDocuments] = useState<DocumentEntry[]>([]);
  const [loading, setLoading] = useState(true);
  const [uploading, setUploading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const load = useCallback(async () => {
    if (!org) return;
    setLoading(true);
    try {
      const data = await api.get<{ items: DocumentEntry[] }>(`/organizations/${org.id}/documents`);
      setDocuments(data.items);
    } catch (err) {
      setError(err instanceof ApiError ? String(err.detail) : "Failed to load documents");
    } finally {
      setLoading(false);
    }
  }, [org]);

  useEffect(() => {
    void load();
  }, [load]);

  async function upload(file: File) {
    if (!org) return;
    setUploading(true);
    setError(null);
    try {
      await api.postFile(`/organizations/${org.id}/documents`, file);
      await load();
    } catch (err) {
      setError(err instanceof ApiError ? String(err.detail) : "Upload failed");
    } finally {
      setUploading(false);
    }
  }

  async function remove(id: string) {
    await api.delete(`/documents/${id}`);
    await load();
  }

  return (
    <div className="mx-auto max-w-3xl">
      <h1 className="text-xl font-semibold text-foreground">Documents</h1>
      <p className="mt-1 text-sm text-foreground-muted">Upload real documents to ground your agents' answers.</p>

      {error && <p className="mt-4 rounded-lg bg-danger-soft px-3 py-2 text-sm text-danger">{error}</p>}

      <label className="mt-6 flex cursor-pointer flex-col items-center justify-center gap-2 rounded-xl border-2 border-dashed border-border-strong bg-surface p-8 text-center hover:border-accent">
        <span className="text-2xl" aria-hidden="true">📤</span>
        <span className="text-sm font-medium text-foreground">{uploading ? "Uploading…" : "Click to upload a document"}</span>
        <span className="text-xs text-foreground-muted">PDF, DOCX, TXT, Markdown, HTML, CSV, JSON, and more</span>
        <input type="file" className="hidden" disabled={uploading} onChange={(e) => e.target.files?.[0] && void upload(e.target.files[0])} />
      </label>

      <div className="mt-6">
        <h2 className="mb-2 text-sm font-semibold text-foreground">Your documents</h2>
        {loading ? (
          <p className="text-sm text-foreground-muted">Loading…</p>
        ) : documents.length === 0 ? (
          <p className="text-sm text-foreground-muted">No documents yet.</p>
        ) : (
          <div className="flex flex-col gap-2">
            {documents.map((doc) => (
              <div key={doc.id} className="flex items-center justify-between rounded-lg border border-border bg-surface p-3">
                <div>
                  <p className="text-sm font-medium text-foreground">{doc.name}</p>
                  <p className="text-xs text-foreground-muted">{formatSize(doc.file_size)} · {doc.file_type} · {doc.status}</p>
                </div>
                <button type="button" onClick={() => void remove(doc.id)} className="text-xs font-medium text-danger hover:underline">Delete</button>
              </div>
            ))}
          </div>
        )}
      </div>
    </div>
  );
}
