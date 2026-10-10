"use client";

import LoadingState from "@/components/LoadingState";
import { useCallback, useEffect, useState } from "react";
import { api, ApiError } from "@/lib/api";
import { useCurrentOrg } from "@/lib/useCurrentOrg";
import { useTranslation } from "@/lib/i18n";

interface DocumentEntry {
  id: string;
  name: string;
  file_size: number;
  file_type: string;
  status: string;
}

const PROCESSING_STATUSES = new Set(["pending", "processing", "uploading", "indexing", "queued"]);

function formatSize(bytes: number): string {
  if (bytes < 1024) return `${bytes} B`;
  if (bytes < 1024 * 1024) return `${(bytes / 1024).toFixed(1)} KB`;
  return `${(bytes / (1024 * 1024)).toFixed(1)} MB`;
}

export default function DocumentsPage() {
  const { org } = useCurrentOrg();
  const { t } = useTranslation();
  const [documents, setDocuments] = useState<DocumentEntry[]>([]);
  const [loading, setLoading] = useState(true);
  const [uploading, setUploading] = useState(false);
  const [dragging, setDragging] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const load = useCallback(async () => {
    if (!org) return;
    setLoading(true);
    try {
      const data = await api.get<{ items: DocumentEntry[] }>(`/organizations/${org.id}/documents`);
      setDocuments(data.items);
    } catch (err) {
      setError(err instanceof ApiError ? String(err.detail) : t("documents.error_load"));
    } finally {
      setLoading(false);
    }
  }, [org, t]);

  useEffect(() => {
    // eslint-disable-next-line react-hooks/set-state-in-effect -- justified: syncing with a real external system (the backend API) after mount/param change, not a value derivable from props/state.
    void load();
  }, [load]);

  // Spec 2.2.3: while some documents are still being processed, refresh the list every few seconds so the status moves on its own.
  const inProgress = documents.some((doc) => PROCESSING_STATUSES.has(doc.status.toLowerCase()));
  useEffect(() => {
    if (!inProgress) return;
    const timer = window.setInterval(() => void load(), 4000);
    return () => window.clearInterval(timer);
  }, [inProgress, load]);

  // Spec 2.2.1 / 2.2.2: several files at once, chosen in the picker or dropped on the zone. Each file is sent on its own so one rejected file does not block the others.
  async function uploadMany(files: File[]) {
    if (!org || files.length === 0) return;
    setUploading(true);
    setError(null);
    const failures: string[] = [];
    for (const file of files) {
      try {
        await api.postFile(`/organizations/${org.id}/documents`, file);
      } catch (err) {
        failures.push(`${file.name}: ${err instanceof ApiError ? String(err.detail) : t("documents.error_upload")}`);
      }
    }
    if (failures.length > 0) setError(failures.join(" | "));
    await load();
    setUploading(false);
  }

  async function remove(id: string) {
    await api.delete(`/documents/${id}`);
    await load();
  }

  return (
    <div className="mx-auto max-w-3xl">
      <h1 className="text-xl font-semibold text-foreground">{t("documents.title")}</h1>
      <p className="mt-1 text-sm text-foreground-muted">{t("documents.subtitle")}</p>

      {error && <p className="mt-4 rounded-lg bg-danger-soft px-3 py-2 text-sm text-danger">{error}</p>}

      <label
        data-testid="drop-zone"
        onDragOver={(e) => { e.preventDefault(); setDragging(true); }}
        onDragLeave={() => setDragging(false)}
        onDrop={(e) => { e.preventDefault(); setDragging(false); void uploadMany(Array.from(e.dataTransfer.files)); }}
        className={`mt-6 flex cursor-pointer flex-col items-center justify-center gap-2 rounded-xl border-2 border-dashed bg-surface p-8 text-center hover:border-accent ${dragging ? "border-accent" : "border-border-strong"}`}
      >
        <span className="text-sm font-medium text-foreground">{uploading ? t("documents.uploading") : t("documents.upload_prompt")}</span>
        <span className="text-xs text-foreground-muted">{t("documents.supported_formats")}</span>
        <input type="file" multiple className="hidden" disabled={uploading} onChange={(e) => { const files = Array.from(e.target.files ?? []); e.target.value = ""; void uploadMany(files); }} />
      </label>

      <div className="mt-6">
        <h2 className="mb-2 text-sm font-semibold text-foreground">{t("documents.your_documents")}</h2>
        {loading ? (
          <LoadingState fullScreen={false} />
        ) : documents.length === 0 ? (
          <p className="text-sm text-foreground-muted">{t("documents.empty")}</p>
        ) : (
          <div className="flex flex-col gap-2">
            {documents.map((doc) => (
              <div key={doc.id} className="flex items-center justify-between rounded-lg border border-border bg-surface p-3">
                <div>
                  <p className="text-sm font-medium text-foreground">{doc.name}</p>
                  <p className="text-xs text-foreground-muted">{formatSize(doc.file_size)} · {doc.file_type} · {doc.status}{PROCESSING_STATUSES.has(doc.status.toLowerCase()) ? " …" : ""}</p>
                </div>
                <button type="button" onClick={() => void remove(doc.id)} className="text-xs font-medium text-danger hover:underline">{t("documents.delete")}</button>
              </div>
            ))}
          </div>
        )}
      </div>
    </div>
  );
}
