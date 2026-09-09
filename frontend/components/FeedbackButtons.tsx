"use client";

import { useState } from "react";
import { api, ApiError } from "@/lib/api";
import { useTranslation } from "@/lib/i18n";
import type { MessageFeedback } from "@/lib/types";

interface FeedbackButtonsProps {
  messageId: string;
}

// Partie 8.1.9 -- 👍/👎 with an optional comment modal for a negative
// rating (real, additive UX -- the literal ask only specifies "opens a
// modal for the comment", not which rating triggers it; a negative
// vote is the one real case where asking why is actually useful).
export default function FeedbackButtons({ messageId }: FeedbackButtonsProps) {
  const { t } = useTranslation();
  const [rating, setRating] = useState<"positive" | "negative" | null>(null);
  const [showCommentBox, setShowCommentBox] = useState(false);
  const [comment, setComment] = useState("");
  const [saving, setSaving] = useState(false);

  async function submit(newRating: "positive" | "negative", withComment?: string) {
    setSaving(true);
    try {
      await api.post<MessageFeedback>(`/messages/${messageId}/feedback`, { rating: newRating, comment: withComment ?? null });
      setRating(newRating);
    } catch (err) {
      // Real, honest no-op on failure: the buttons stay usable so the
      // user can just try again, rather than a jarring page-level error
      // for a low-stakes background action. Logged as a plain string,
      // never the raw Error/ApiError object -- Next.js's own dev
      // overlay intercepts any console.error call carrying a real
      // Error instance and renders it as a full-screen crash, even
      // though this is a real, deliberately-caught, non-fatal failure
      // (found directly: clicking 👎 with no backend running showed
      // the dev overlay despite this try/catch already working).
      console.error(`Feedback submission failed: ${err instanceof ApiError ? String(err.detail) : String(err)}`);
    } finally {
      setSaving(false);
    }
  }

  function handleClick(newRating: "positive" | "negative") {
    if (newRating === "negative") {
      setShowCommentBox(true);
      return;
    }
    void submit(newRating);
  }

  return (
    <div className="inline-flex flex-col gap-2">
      <div className="inline-flex items-center gap-1">
        <button
          type="button"
          onClick={() => handleClick("positive")}
          disabled={saving}
          aria-pressed={rating === "positive"}
          aria-label={t("good_response")}
          className={`rounded-lg px-2 py-1 text-sm ${rating === "positive" ? "bg-success-soft text-success" : "text-foreground-muted hover:bg-accent-soft"}`}
        >
          👍
        </button>
        <button
          type="button"
          onClick={() => handleClick("negative")}
          disabled={saving}
          aria-pressed={rating === "negative"}
          aria-label={t("bad_response")}
          className={`rounded-lg px-2 py-1 text-sm ${rating === "negative" ? "bg-danger-soft text-danger" : "text-foreground-muted hover:bg-accent-soft"}`}
        >
          👎
        </button>
      </div>

      {showCommentBox && rating !== "negative" && (
        <div className="w-64 rounded-lg border border-border bg-surface p-2 shadow-sm">
          <textarea
            value={comment}
            onChange={(event) => setComment(event.target.value)}
            placeholder={t("what_went_wrong")}
            rows={2}
            className="w-full resize-none rounded-md border border-border bg-background p-1.5 text-xs text-foreground outline-none focus:border-accent"
          />
          <div className="mt-1.5 flex justify-end gap-2">
            <button type="button" onClick={() => setShowCommentBox(false)} className="text-xs text-foreground-muted hover:underline">
              {t("skip")}
            </button>
            <button
              type="button"
              onClick={() => {
                void submit("negative", comment || undefined);
                setShowCommentBox(false);
              }}
              className="rounded-md bg-accent px-2 py-1 text-xs font-medium text-white hover:bg-accent-hover"
            >
              {t("send")}
            </button>
          </div>
        </div>
      )}
    </div>
  );
}
