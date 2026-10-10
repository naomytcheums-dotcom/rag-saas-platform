"use client";

import { useState } from "react";
import { api, ApiError, fileUrl } from "@/lib/api";
import { useTranslation } from "@/lib/i18n";

const FORMATS = ["pdf", "docx", "json", "markdown"] as const;

async function download(conversationId: string, format: (typeof FORMATS)[number]): Promise<void> {
  const token = window.localStorage.getItem("access_token");
  const response = await fetch(fileUrl(`/conversations/${conversationId}/export/${format}`), {
    credentials: "include",
    headers: token ? { Authorization: `Bearer ${token}` } : {},
  });
  if (!response.ok) throw new ApiError(response.status, await response.text());
  const blob = await response.blob();
  const link = document.createElement("a");
  link.href = URL.createObjectURL(blob);
  link.download = `conversation.${format === "markdown" ? "md" : format}`;
  link.click();
  URL.revokeObjectURL(link.href);
}

/** Specs 8.1.14 (export PDF / DOCX / JSON / Markdown) and 8.1.16 (public / private): the two conversation-level controls of the chat header. */
export default function ConversationTools({ conversationId }: { conversationId: string | null }) {
  const { t } = useTranslation();
  const [isPublic, setIsPublic] = useState(false);
  const [error, setError] = useState<string | null>(null);
  if (!conversationId) return null;

  async function exportAs(format: (typeof FORMATS)[number]) {
    setError(null);
    try {
      await download(conversationId as string, format);
    } catch {
      setError(t("chat.export_error"));
    }
  }

  async function toggleVisibility() {
    setError(null);
    try {
      const updated = await api.patch<{ is_public: boolean }>(`/conversations/${conversationId}/visibility`, { is_public: !isPublic });
      setIsPublic(updated.is_public);
    } catch (err) {
      setError(err instanceof ApiError ? String(err.detail) : t("chat.visibility_error"));
    }
  }

  return (
    <div className="flex items-center gap-2 text-xs">
      <label className="flex items-center gap-1">
        <span className="text-foreground-muted">{t("chat.export")}</span>
        <select
          aria-label={t("chat.export")}
          value=""
          onChange={(e) => e.target.value && void exportAs(e.target.value as (typeof FORMATS)[number])}
          className="rounded-lg border border-border bg-background px-1 py-0.5"
        >
          <option value="">…</option>
          {FORMATS.map((f) => <option key={f} value={f}>{f.toUpperCase()}</option>)}
        </select>
      </label>
      <button type="button" aria-pressed={isPublic} onClick={() => void toggleVisibility()} className="rounded-lg border border-border px-2 py-0.5 hover:bg-surface-muted">
        {isPublic ? t("chat.visibility_public") : t("chat.visibility_private")}
      </button>
      {error && <span role="alert" className="text-danger">{error}</span>}
    </div>
  );
}
