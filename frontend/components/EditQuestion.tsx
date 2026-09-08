"use client";

import { useState } from "react";
import { api, ApiError } from "@/lib/api";
import type { ConversationMessage } from "@/lib/types";

interface EditQuestionProps {
  conversationId: string;
  messageId: string;
  initialContent: string;
  onSaved: (newAnswer: ConversationMessage) => void;
  onCancel: () => void;
}

// Partie 8.1.7 -- edits a user question, then regenerates the answer.
// Ctrl+Enter saves, Escape cancels (the literal ask's own shortcuts).
export default function EditQuestion({ conversationId, messageId, initialContent, onSaved, onCancel }: EditQuestionProps) {
  const [content, setContent] = useState(initialContent);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  async function save() {
    setLoading(true);
    setError(null);
    try {
      const newAnswer = await api.post<ConversationMessage>(
        `/conversations/${conversationId}/messages/${messageId}/edit`,
        { content },
      );
      onSaved(newAnswer);
    } catch (err) {
      setError(err instanceof ApiError ? String(err.detail) : "Failed to save edit");
    } finally {
      setLoading(false);
    }
  }

  return (
    <div className="rounded-xl border border-border-strong bg-surface p-3">
      <textarea
        value={content}
        onChange={(event) => setContent(event.target.value)}
        onKeyDown={(event) => {
          if (event.key === "Enter" && (event.ctrlKey || event.metaKey)) save();
          if (event.key === "Escape") onCancel();
        }}
        rows={3}
        autoFocus
        className="w-full resize-none rounded-lg border border-border bg-background p-2 text-sm text-foreground outline-none focus:border-accent"
      />
      <div className="mt-2 flex items-center justify-between">
        <span className="text-xs text-foreground-muted">Ctrl+Enter to save · Esc to cancel</span>
        <div className="flex gap-2">
          <button type="button" onClick={onCancel} className="rounded-lg px-3 py-1 text-xs font-medium text-foreground-muted hover:bg-surface-muted">
            Cancel
          </button>
          <button
            type="button"
            onClick={save}
            disabled={loading || content.trim() === ""}
            className="rounded-lg bg-accent px-3 py-1 text-xs font-medium text-white hover:bg-accent-hover disabled:opacity-50"
          >
            {loading ? "Saving…" : "Save"}
          </button>
        </div>
      </div>
      {error && <p className="mt-1 text-xs text-danger">{error}</p>}
    </div>
  );
}
