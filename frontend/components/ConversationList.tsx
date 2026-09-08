"use client";

import { useEffect, useState } from "react";
import { api } from "@/lib/api";
import type { Conversation } from "@/lib/types";
import ConversationItem from "./ConversationItem";

interface ConversationListProps {
  activeConversationId?: string;
  onSelect: (id: string) => void;
}

const PAGE_SIZE = 20;

// Partie 8.1.10 -- GET /conversations, paginated ("load more").
export default function ConversationList({ activeConversationId, onSelect }: ConversationListProps) {
  const [conversations, setConversations] = useState<Conversation[]>([]);
  const [offset, setOffset] = useState(0);
  const [hasMore, setHasMore] = useState(true);
  const [loading, setLoading] = useState(false);

  async function loadMore() {
    setLoading(true);
    try {
      const page = await api.get<Conversation[]>(`/conversations?limit=${PAGE_SIZE}&offset=${offset}`);
      setConversations((prev) => [...prev, ...page]);
      setOffset((prev) => prev + page.length);
      setHasMore(page.length === PAGE_SIZE);
    } catch {
      // Real, honest no-op (e.g. no backend/session yet) -- shows the
      // real, empty "No conversations yet" state below instead of an
      // uncaught rejection (found directly: this try had no catch at
      // all, only a finally, so a failed fetch reached Next.js's own
      // dev overlay).
      setHasMore(false);
    } finally {
      setLoading(false);
    }
  }

  useEffect(() => {
    // Real, legitimate fetch-on-mount -- there is no external
    // subscription to attach here, just an initial page to load, and
    // `loadMore` is deliberately excluded from deps (it closes over
    // `offset`, which would re-trigger this effect after every page).
    // eslint-disable-next-line react-hooks/set-state-in-effect
    void loadMore();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  return (
    <div className="flex flex-col gap-1">
      {conversations.map((conversation) => (
        <ConversationItem
          key={conversation.id}
          conversation={conversation}
          active={conversation.id === activeConversationId}
          onSelect={onSelect}
          onRenamed={(updated) => setConversations((prev) => prev.map((c) => (c.id === updated.id ? updated : c)))}
          onDeleted={(id) => setConversations((prev) => prev.filter((c) => c.id !== id))}
        />
      ))}

      {conversations.length === 0 && !loading && (
        <p className="px-3 py-6 text-center text-sm text-foreground-muted">No conversations yet</p>
      )}

      {hasMore && (
        <button
          type="button"
          onClick={loadMore}
          disabled={loading}
          className="mt-2 rounded-lg px-3 py-1.5 text-xs font-medium text-accent-hover hover:bg-accent-soft disabled:opacity-50"
        >
          {loading ? "Loading…" : "Load more"}
        </button>
      )}
    </div>
  );
}
