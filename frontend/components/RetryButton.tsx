"use client";

import { useState } from "react";
import { api, ApiError } from "@/lib/api";
import { useTranslation } from "@/lib/i18n";
import type { ConversationMessage } from "@/lib/types";

interface RetryButtonProps {
  conversationId: string;
  messageId: string;
  maxAttempts?: number;
  onRetried: (message: ConversationMessage) => void;
}

// Partie 8.1.8 -- retries a question with no answer yet. Disables
// itself once the real backend's own RETRY_MAX_ATTEMPTS is reached
// (the retry_count comes back on the request body's own response, see
// RetryResponse in api/schemas/message_actions.py).
export default function RetryButton({ conversationId, messageId, maxAttempts = 3, onRetried }: RetryButtonProps) {
  const { t } = useTranslation();
  const [attempts, setAttempts] = useState(0);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const exhausted = attempts >= maxAttempts;

  async function handleRetry() {
    setLoading(true);
    setError(null);
    try {
      const result = await api.post<{ message: ConversationMessage; retry_count: number }>(
        `/conversations/${conversationId}/messages/${messageId}/retry`,
      );
      setAttempts(result.retry_count);
      onRetried(result.message);
    } catch (err) {
      setError(err instanceof ApiError ? String(err.detail) : "Retry failed");
    } finally {
      setLoading(false);
    }
  }

  return (
    <div className="inline-flex items-center gap-2">
      <button
        type="button"
        onClick={handleRetry}
        disabled={loading || exhausted}
        className="inline-flex items-center gap-1.5 rounded-lg px-2 py-1 text-xs font-medium text-foreground-muted hover:bg-accent-soft hover:text-accent-hover disabled:opacity-50"
      >
        {loading ? t("retrying") : exhausted ? t("retry_limit_reached") : t("retry_with_count", { attempts, max: maxAttempts })}
      </button>
      {error && <span className="text-xs text-danger">{error}</span>}
    </div>
  );
}
