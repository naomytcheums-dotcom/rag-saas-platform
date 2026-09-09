"use client";

import { useState } from "react";
import { api, ApiError } from "@/lib/api";
import { useTranslation } from "@/lib/i18n";

interface DeleteConversationProps {
  conversationId: string;
  onDeleted: () => void;
}

// Partie 8.1.13 -- soft-deletes via DELETE /conversations/{id} (the
// backend keeps it recoverable for CONVERSATION_DELETION_GRACE_PERIOD
// days before a real Celery purge). Confirms before deleting, since
// this is a real destructive-looking action from the user's own point
// of view even though it's reversible server-side.
export default function DeleteConversation({ conversationId, onDeleted }: DeleteConversationProps) {
  const { t } = useTranslation();
  const [confirming, setConfirming] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [notice, setNotice] = useState(false);

  async function handleDelete() {
    try {
      await api.delete(`/conversations/${conversationId}`);
      setNotice(true);
      onDeleted();
    } catch (err) {
      setError(err instanceof ApiError ? String(err.detail) : "Could not delete");
    } finally {
      setConfirming(false);
    }
  }

  if (notice) {
    return <span className="text-xs text-success">{t("conversation_deleted")}</span>;
  }

  if (confirming) {
    return (
      <span className="inline-flex items-center gap-2 text-xs">
        <span className="text-foreground-muted">{t("delete_this_conversation")}</span>
        <button type="button" onClick={handleDelete} className="font-medium text-danger hover:underline">
          {t("delete")}
        </button>
        <button type="button" onClick={() => setConfirming(false)} className="text-foreground-muted hover:underline">
          {t("cancel")}
        </button>
      </span>
    );
  }

  return (
    <div>
      <button
        type="button"
        onClick={() => setConfirming(true)}
        aria-label={t("delete_conversation")}
        className="rounded-lg px-2 py-1 text-xs text-foreground-muted hover:bg-danger-soft hover:text-danger"
      >
        {t("delete")}
      </button>
      {error && <p className="text-xs text-danger">{error}</p>}
    </div>
  );
}
