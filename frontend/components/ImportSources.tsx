"use client";

import { useState } from "react";
import { api, ApiError } from "@/lib/api";
import { useTranslation } from "@/lib/i18n";

type Source = "url" | "sitemap" | "github" | "github_issues" | "google_drive" | "google_docs" | "notion" | "confluence" | "onedrive";

const SOURCES: { key: Source; path: string; field: string; body: (value: string) => Record<string, unknown> }[] = [
  { key: "url", path: "documents/url", field: "https://example.com/page", body: (url) => ({ url }) },
  { key: "sitemap", path: "documents/sitemap", field: "https://example.com/sitemap.xml", body: (url) => ({ url }) },
  { key: "github", path: "documents/github/repo", field: "https://github.com/owner/repo", body: (repo_url) => ({ repo_url }) },
  { key: "github_issues", path: "documents/github/issues", field: "https://github.com/owner/repo", body: (repo_url) => ({ repo_url }) },
  { key: "google_drive", path: "documents/google-drive", field: "Google Drive folder or file id", body: (drive_id) => ({ drive_id }) },
  { key: "google_docs", path: "documents/google-docs", field: "Google Docs / Sheets / Slides URL or id", body: (document_url_or_id) => ({ document_url_or_id }) },
  { key: "notion", path: "documents/notion", field: "Notion page or database URL / id", body: (url_or_id) => ({ url_or_id, kind: "page" }) },
  { key: "confluence", path: "documents/confluence", field: "Confluence page or space URL / id", body: (url_or_id) => ({ url_or_id }) },
  { key: "onedrive", path: "documents/onedrive", field: "OneDrive folder or file id", body: (folder_id) => ({ folder_id }) },
];

/** Specs 2.1.10 to 2.1.18: import documents from a web page, a sitemap, GitHub (repository or issues), Google Drive, Google Docs, Notion, Confluence
 * or OneDrive. The import runs in the background; the documents appear in the list below with their live status. The provider credentials are
 * platform settings (not per user), so each source only needs the address or id. */
export default function ImportSources({ orgId, onImported }: { orgId: string; onImported: () => void }) {
  const { t } = useTranslation();
  const [source, setSource] = useState<Source>("url");
  const [value, setValue] = useState("");
  const [busy, setBusy] = useState(false);
  const [message, setMessage] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);
  const current = SOURCES.find((s) => s.key === source) ?? SOURCES[0];

  async function submit(event: React.FormEvent) {
    event.preventDefault();
    setBusy(true);
    setError(null);
    setMessage(null);
    try {
      await api.post(`/organizations/${orgId}/${current.path}`, current.body(value.trim()));
      setMessage(t("documents.import_started"));
      setValue("");
      onImported();
    } catch (err) {
      setError(err instanceof ApiError ? String(err.detail) : t("documents.import_error"));
    } finally {
      setBusy(false);
    }
  }

  return (
    <form onSubmit={submit} className="mt-4 rounded-xl border border-border bg-surface p-4" aria-label={t("documents.import_title")}>
      <h2 className="text-sm font-semibold text-foreground">{t("documents.import_title")}</h2>
      <div className="mt-2 flex flex-wrap gap-2">
        <select aria-label={t("documents.import_source")} value={source} onChange={(e) => { setSource(e.target.value as Source); setValue(""); }} className="rounded-lg border border-border bg-background px-2 py-1 text-sm">
          {SOURCES.map((s) => <option key={s.key} value={s.key}>{t(`documents.source_${s.key}`)}</option>)}
        </select>
        <input
          aria-label={t("documents.import_target")}
          placeholder={current.field}
          value={value}
          onChange={(e) => setValue(e.target.value)}
          required
          className="min-w-[260px] flex-1 rounded-lg border border-border bg-background px-2 py-1 text-sm"
        />
        <button type="submit" disabled={busy || !value.trim()} className="rounded-lg bg-accent px-3 py-1 text-sm font-medium text-white disabled:opacity-50">{t("documents.import_button")}</button>
      </div>
      {message && <p role="status" className="mt-2 text-xs text-foreground-muted">{message}</p>}
      {error && <p role="alert" className="mt-2 text-xs text-danger">{error}</p>}
    </form>
  );
}
