"use client";

import { useState } from "react";
import { ApiError } from "@/lib/api";
import { addReview } from "@/lib/services/plugins";

interface PluginReviewFormProps {
  orgId: string;
  pluginId: string;
  onSubmitted?: () => void;
  onError?: (message: string) => void;
}

// Partie 16 (ter) -- POST /organizations/{org_id}/plugins/{id}/reviews.
// Re-submitting updates the existing review in place (server-side
// upsert, api/services/plugins.py's own submit_review).
export default function PluginReviewForm({ orgId, pluginId, onSubmitted, onError }: PluginReviewFormProps) {
  const [rating, setRating] = useState(5);
  const [comment, setComment] = useState("");
  const [submitting, setSubmitting] = useState(false);

  async function submit() {
    setSubmitting(true);
    try {
      await addReview(orgId, pluginId, { rating, comment: comment || null });
      setComment("");
      onSubmitted?.();
    } catch (err) {
      onError?.(err instanceof ApiError ? String(err.detail) : "Failed to submit review");
    } finally {
      setSubmitting(false);
    }
  }

  return (
    <div className="flex flex-wrap items-center gap-2">
      <select value={rating} onChange={(e) => setRating(Number(e.target.value))} className="rounded-lg border border-border bg-background px-2.5 py-1 text-xs">
        {[5, 4, 3, 2, 1].map((n) => (
          <option key={n} value={n}>{n} / 5</option>
        ))}
      </select>
      <input value={comment} onChange={(e) => setComment(e.target.value)} placeholder="Comment (optional)" className="flex-1 rounded-lg border border-border bg-background px-2.5 py-1 text-xs outline-none focus:border-accent" />
      <button type="button" disabled={submitting} onClick={() => void submit()} className="rounded-lg bg-accent px-2.5 py-1 text-xs font-medium text-white hover:bg-accent-hover disabled:opacity-50">
        {submitting ? "Submitting…" : "Rate"}
      </button>
    </div>
  );
}
