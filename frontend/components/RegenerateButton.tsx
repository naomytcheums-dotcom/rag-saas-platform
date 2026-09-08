"use client";

import { useState } from "react";
import { api, ApiError } from "@/lib/api";
import type { ConversationMessage } from "@/lib/types";

interface RegenerateButtonProps {
  conversationId: string;
  messageId: string;
  onRegenerated: (message: ConversationMessage) => void;
}

// Partie 8.1.6 -- POST /conversations/{id}/messages/{id}/regenerate.
export default function RegenerateButton({ conversationId, messageId, onRegenerated }: RegenerateButtonProps) {
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  async function handleRegenerate() {
    setLoading(true);
    setError(null);
    try {
      const message = await api.post<ConversationMessage>(
        `/conversations/${conversationId}/messages/${messageId}/regenerate`,
        {},
      );
      onRegenerated(message);
    } catch (err) {
      setError(err instanceof ApiError ? String(err.detail) : "Regeneration failed");
    } finally {
      setLoading(false);
    }
  }

  return (
    <div className="inline-flex items-center gap-2">
      <button
        type="button"
        onClick={handleRegenerate}
        disabled={loading}
        aria-busy={loading}
        className="inline-flex items-center gap-1.5 rounded-lg px-2 py-1 text-xs font-medium text-foreground-muted hover:bg-accent-soft hover:text-accent-hover disabled:opacity-50"
      >
        {loading ? (
          <span className="h-3 w-3 animate-spin rounded-full border-2 border-accent border-t-transparent" />
        ) : (
          "Regenerate"
        )}
      </button>
      {error && <span className="text-xs text-danger">{error}</span>}
    </div>
  );
}
