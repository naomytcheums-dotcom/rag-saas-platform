"use client";

import { useCallback, useEffect, useState } from "react";
import { api, ApiError, fileUrl } from "@/lib/api";
import { useTranslation } from "@/lib/i18n";

interface Tag { id: string; name: string; color: string | null }
interface Version { id: string; version_number: number; file_size: number; created_at: string }
interface HistoryEntry { id: string; action: string; timestamp: string }
interface DuplicateEntry { id: string; name: string }

/** Document actions that the backend has had for a while but no screen offered: tags (2.2.6), versions and replacement (2.2.7, 2.2.8), preview (2.2.4),
 * manual re-indexing (2.2.9), modification history (2.2.10) and duplicate detection (2.2.12). One panel per document, opened from the documents page. */
export default function DocumentDetails({ documentId, orgId, onChanged }: { documentId: string; orgId: string; onChanged: () => void }) {
  const { t } = useTranslation();
  const [orgTags, setOrgTags] = useState<Tag[]>([]);
  const [tags, setTags] = useState<Tag[]>([]);
  const [versions, setVersions] = useState<Version[]>([]);
  const [history, setHistory] = useState<HistoryEntry[]>([]);
  const [duplicates, setDuplicates] = useState<DuplicateEntry[] | null>(null);
  const [newTag, setNewTag] = useState("");
  const [message, setMessage] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);

  const load = useCallback(async () => {
    try {
      const [all, mine, v, h] = await Promise.all([
        api.get<Tag[]>(`/organizations/${orgId}/tags`),
        api.get<Tag[]>(`/documents/${documentId}/tags`),
        api.get<Version[]>(`/documents/${documentId}/versions`),
        api.get<HistoryEntry[]>(`/documents/${documentId}/history`),
      ]);
      setOrgTags(all); setTags(mine); setVersions(v); setHistory(h);
    } catch (err) {
      setError(err instanceof ApiError ? String(err.detail) : t("documents.detail_error"));
    }
  }, [documentId, orgId, t]);

  useEffect(() => {
    // eslint-disable-next-line react-hooks/set-state-in-effect -- justified: syncing with the backend API when the panel opens.
    void load();
  }, [load]);

  async function run(action: () => Promise<unknown>, done?: string) {
    setError(null);
    setMessage(null);
    try {
      await action();
      if (done) setMessage(done);
      await load();
    } catch (err) {
      setError(err instanceof ApiError ? String(err.detail) : t("documents.detail_error"));
    }
  }

  async function addTag(tagId: string) {
    await api.post(`/documents/${documentId}/tags`, { tag_id: tagId });
  }

  async function createAndAddTag() {
    const created = await api.post<Tag>(`/organizations/${orgId}/tags`, { name: newTag.trim() });
    await api.post(`/documents/${documentId}/tags`, { tag_id: created.id });
    setNewTag("");
  }

  async function preview() {
    setError(null);
    const token = window.localStorage.getItem("access_token");
    const response = await fetch(fileUrl(`/documents/${documentId}/preview`), { credentials: "include", headers: token ? { Authorization: `Bearer ${token}` } : {} });
    if (!response.ok) {
      setError(t("documents.detail_error"));
      return;
    }
    const url = URL.createObjectURL(await response.blob());
    window.open(url, "_blank", "noopener");
  }

  const free = orgTags.filter((tag) => !tags.some((mine) => mine.id === tag.id));
  const btn = "rounded-lg border border-border px-2 py-1 text-xs hover:bg-surface-muted disabled:opacity-50";

  return (
    <div className="mt-3 space-y-3 border-t border-border pt-3 text-sm">
      {error && <p role="alert" className="text-danger">{error}</p>}
      {message && <p role="status" className="text-foreground-muted">{message}</p>}

      <div className="flex flex-wrap gap-2">
        <button type="button" className={btn} onClick={() => void preview()}>{t("documents.preview")}</button>
        <button type="button" className={btn} onClick={() => void run(() => api.post(`/documents/${documentId}/reindex`), t("documents.reindex_scheduled"))}>{t("documents.reindex")}</button>
        <button type="button" className={btn} onClick={() => void run(async () => setDuplicates(await api.get<DuplicateEntry[]>(`/documents/${documentId}/duplicates`)))}>{t("documents.find_duplicates")}</button>
        <label className={`${btn} cursor-pointer`}>
          {t("documents.replace")}
          <input type="file" className="hidden" onChange={(e) => { const file = e.target.files?.[0]; e.target.value = ""; if (file) void run(async () => { await api.postFile(`/documents/${documentId}/replace`, file); onChanged(); }, t("documents.replaced")); }} />
        </label>
      </div>

      {duplicates && (
        <p className="text-foreground-muted">{duplicates.length === 0 ? t("documents.no_duplicates") : `${t("documents.duplicates")}: ${duplicates.map((d) => d.name).join(", ")}`}</p>
      )}

      <div>
        <h3 className="text-xs font-semibold text-foreground">{t("documents.tags")}</h3>
        <div className="mt-1 flex flex-wrap items-center gap-1">
          {tags.length === 0 && <span className="text-foreground-muted">{t("documents.no_tags")}</span>}
          {tags.map((tag) => (
            <span key={tag.id} className="inline-flex items-center gap-1 rounded-full bg-accent-soft px-2 py-0.5 text-xs">
              {tag.name}
              <button type="button" aria-label={`${t("documents.remove_tag")} ${tag.name}`} onClick={() => void run(() => api.delete(`/documents/${documentId}/tags/${tag.id}`))}>×</button>
            </span>
          ))}
        </div>
        <div className="mt-2 flex flex-wrap gap-2">
          {free.length > 0 && (
            <select aria-label={t("documents.add_tag")} value="" onChange={(e) => e.target.value && void run(() => addTag(e.target.value))} className="rounded-lg border border-border bg-background px-1 py-0.5 text-xs">
              <option value="">{t("documents.add_tag")}</option>
              {free.map((tag) => <option key={tag.id} value={tag.id}>{tag.name}</option>)}
            </select>
          )}
          <input value={newTag} onChange={(e) => setNewTag(e.target.value)} aria-label={t("documents.new_tag")} placeholder={t("documents.new_tag")} className="rounded-lg border border-border bg-background px-2 py-0.5 text-xs" />
          <button type="button" disabled={!newTag.trim()} className={btn} onClick={() => void run(createAndAddTag)}>{t("documents.create_tag")}</button>
        </div>
      </div>

      <div>
        <h3 className="text-xs font-semibold text-foreground">{t("documents.versions")}</h3>
        <ul className="mt-1 list-disc pl-5 text-foreground-muted">
          {versions.length === 0 ? <li>{t("documents.no_versions")}</li> : versions.map((v) => <li key={v.id}>v{v.version_number} · {new Date(v.created_at).toLocaleString()}</li>)}
        </ul>
      </div>

      <div>
        <h3 className="text-xs font-semibold text-foreground">{t("documents.history")}</h3>
        <ul className="mt-1 list-disc pl-5 text-foreground-muted">
          {history.length === 0 ? <li>{t("documents.no_history")}</li> : history.slice(0, 20).map((h) => <li key={h.id}>{h.action} · {new Date(h.timestamp).toLocaleString()}</li>)}
        </ul>
      </div>
    </div>
  );
}
