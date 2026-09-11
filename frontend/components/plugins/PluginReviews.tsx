"use client";

import { useCallback, useEffect, useState } from "react";
import { ApiError } from "@/lib/api";
import { deleteReview, listReviews } from "@/lib/services/plugins";
import type { PluginReview } from "@/lib/types";

interface PluginReviewsProps {
  pluginId: string;
  currentUserId?: string;
  onError?: (message: string) => void;
  refreshKey?: number;
}

// Partie 16 (ter) -- GET /marketplace/plugins/{id}/reviews + DELETE
// /marketplace/reviews/{id} (owner-only, enforced server-side too).
export default function PluginReviews({ pluginId, currentUserId, onError, refreshKey }: PluginReviewsProps) {
  const [reviews, setReviews] = useState<PluginReview[]>([]);

  const load = useCallback(async () => {
    try {
      setReviews(await listReviews(pluginId));
    } catch (err) {
      onError?.(err instanceof ApiError ? String(err.detail) : "Failed to load reviews");
    }
  }, [pluginId, onError]);

  useEffect(() => {
    // eslint-disable-next-line react-hooks/set-state-in-effect
    void load();
  }, [load, refreshKey]);

  async function remove(reviewId: string) {
    try {
      await deleteReview(reviewId);
      await load();
    } catch (err) {
      onError?.(err instanceof ApiError ? String(err.detail) : "Failed to delete review");
    }
  }

  if (reviews.length === 0) {
    return <p className="text-xs text-foreground-muted">No reviews yet.</p>;
  }

  return (
    <div className="flex flex-col gap-1.5">
      {reviews.map((review) => (
        <div key={review.id} className="flex items-center justify-between rounded-lg bg-background px-2.5 py-1.5 text-xs">
          <span className="text-foreground-muted">{review.rating}/5 — {review.comment ?? "(no comment)"}</span>
          {currentUserId === review.user_id && (
            <button type="button" onClick={() => void remove(review.id)} className="font-medium text-danger hover:underline">Delete</button>
          )}
        </div>
      ))}
    </div>
  );
}
