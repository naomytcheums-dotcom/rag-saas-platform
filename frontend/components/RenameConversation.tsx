"use client";

import { useState } from "react";
import { api, ApiError } from "@/lib/api";
import { useTranslation } from "@/lib/i18n";
import type { Conversation } from "@/lib/types";

interface RenameConversationProps {
  conversation: Conversation;
  onRenamed: (conversation: Conversation) => void;
}

// Partie 8.1.11 -- double-click the title to edit, Enter to save, Esc
// to cancel (the literal ask's own interaction spec).
export default function RenameConversation({ conversation, onRenamed }: RenameConversationProps) {
  const { t } = useTranslation();
  const [editing, setEditing] = useState(false);
  const [title, setTitle] = useState(conversation.title);
  const [error, setError] = useState<string | null>(null);

  async function save() {
    if (title.trim() === conversation.title) {
      setEditing(false);
      return;
    }
    try {
      const updated = await api.patch<Conversation>(`/conversations/${conversation.id}`, { title: title.trim() });
      onRenamed(updated);
      setEditing(false);
      setError(null);
    } catch (err) {
      setError(err instanceof ApiError ? String(err.detail) : "Could not rename");
    }
  }

  if (!editing) {
    return (
      <button
        type="button"
        onDoubleClick={() => setEditing(true)}
        className="truncate text-left text-sm font-medium text-foreground"
        title={t("double_click_to_rename")}
      >
        {conversation.title}
      </button>
    );
  }

  return (
    <div>
      <input
        autoFocus
        value={title}
        onChange={(event) => setTitle(event.target.value)}
        onBlur={save}
        onKeyDown={(event) => {
          if (event.key === "Enter") save();
          if (event.key === "Escape") {
            setTitle(conversation.title);
            setEditing(false);
          }
        }}
        className="w-full rounded-md border border-accent bg-background px-1.5 py-0.5 text-sm text-foreground outline-none"
      />
      {error && <p className="mt-0.5 text-xs text-danger">{error}</p>}
    </div>
  );
}
