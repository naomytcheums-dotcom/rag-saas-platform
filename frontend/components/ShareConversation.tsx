"use client";

import { useState } from "react";
import { api, ApiError } from "@/lib/api";
import type { ConversationShare } from "@/lib/types";

interface ShareConversationProps {
  conversationId: string;
}

// Partie 8.1.15 -- creates a public share link, lets the user copy it
// and optionally set an expiry.
export default function ShareConversation({ conversationId }: ShareConversationProps) {
  const [open, setOpen] = useState(false);
  const [share, setShare] = useState<ConversationShare | null>(null);
  const [expiresInDays, setExpiresInDays] = useState<number | "">("");
  const [loading, setLoading] = useState(false);
  const [copied, setCopied] = useState(false);
  const [error, setError] = useState<string | null>(null);

  async function createShare() {
    setLoading(true);
    setError(null);
    try {
      const expires_at =
        expiresInDays === "" ? null : new Date(Date.now() + Number(expiresInDays) * 86400000).toISOString();
      const result = await api.post<ConversationShare>(`/conversations/${conversationId}/share`, { expires_at });
      setShare(result);
    } catch (err) {
      setError(err instanceof ApiError ? String(err.detail) : "Could not create share link");
    } finally {
      setLoading(false);
    }
  }

  const shareUrl = share ? `${window.location.origin}/share/${share.token}` : "";

  return (
    <div className="relative inline-block">
      <button
        type="button"
        onClick={() => setOpen((prev) => !prev)}
        className="rounded-lg px-2 py-1 text-xs font-medium text-foreground-muted hover:bg-accent-soft hover:text-accent-hover"
      >
        Share
      </button>

      {open && (
        <div className="absolute right-0 z-30 mt-1 w-72 rounded-xl border border-border bg-surface p-3 shadow-md">
          {!share ? (
            <>
              <label className="mb-2 block text-xs text-foreground-muted">
                Expires in (days, optional)
                <input
                  type="number"
                  min={1}
                  value={expiresInDays}
                  onChange={(event) => setExpiresInDays(event.target.value === "" ? "" : Number(event.target.value))}
                  className="mt-1 w-full rounded-md border border-border bg-background px-2 py-1 text-sm text-foreground outline-none focus:border-accent"
                />
              </label>
              <button
                type="button"
                onClick={createShare}
                disabled={loading}
                className="w-full rounded-lg bg-accent px-3 py-1.5 text-xs font-medium text-white hover:bg-accent-hover disabled:opacity-50"
              >
                {loading ? "Creating…" : "Create link"}
              </button>
              {error && <p className="mt-1 text-xs text-danger">{error}</p>}
            </>
          ) : (
            <>
              <p className="mb-2 truncate rounded-md bg-surface-muted px-2 py-1.5 text-xs text-foreground-muted">{shareUrl}</p>
              <button
                type="button"
                onClick={async () => {
                  await navigator.clipboard.writeText(shareUrl);
                  setCopied(true);
                  setTimeout(() => setCopied(false), 2000);
                }}
                className="w-full rounded-lg bg-accent px-3 py-1.5 text-xs font-medium text-white hover:bg-accent-hover"
              >
                {copied ? "Copied!" : "Copy link"}
              </button>
            </>
          )}
        </div>
      )}
    </div>
  );
}
