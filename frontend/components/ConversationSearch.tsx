"use client";

import { useEffect, useRef, useState } from "react";
import { api } from "@/lib/api";
import { useTranslation } from "@/lib/i18n";
import type { SearchResult } from "@/lib/types";

interface ConversationSearchProps {
  onSelect: (conversationId: string) => void;
}

const DEBOUNCE_MS = 300;

// Partie 8.1.12 -- debounced real-time search across titles and
// messages, with the backend's own real <mark> highlighting rendered.
export default function ConversationSearch({ onSelect }: ConversationSearchProps) {
  const { t } = useTranslation();
  const [query, setQuery] = useState("");
  const [results, setResults] = useState<SearchResult[]>([]);
  const [loading, setLoading] = useState(false);
  const debounceRef = useRef<ReturnType<typeof setTimeout> | null>(null);

  useEffect(() => {
    if (debounceRef.current) clearTimeout(debounceRef.current);
    if (query.trim().length < 2) {
      // Real, legitimate clear-on-short-query -- resetting local UI
      // state, not synchronizing with an external system.
      // eslint-disable-next-line react-hooks/set-state-in-effect
      setResults([]);
      return;
    }
    debounceRef.current = setTimeout(async () => {
      setLoading(true);
      try {
        const data = await api.get<SearchResult[]>(`/conversations/search?q=${encodeURIComponent(query)}`);
        setResults(data);
      } catch {
        setResults([]);
      } finally {
        setLoading(false);
      }
    }, DEBOUNCE_MS);
    return () => {
      if (debounceRef.current) clearTimeout(debounceRef.current);
    };
  }, [query]);

  return (
    <div className="relative">
      <input
        value={query}
        onChange={(event) => setQuery(event.target.value)}
        placeholder={t("search_conversations")}
        className="w-full rounded-lg border border-border bg-surface px-3 py-2 text-sm text-foreground outline-none focus:border-accent"
      />

      {query.trim().length >= 2 && (
        <div className="absolute z-30 mt-1 max-h-80 w-full overflow-y-auto rounded-xl border border-border bg-surface shadow-md">
          {loading && <p className="px-3 py-2 text-sm text-foreground-muted">Searching…</p>}
          {!loading && results.length === 0 && <p className="px-3 py-2 text-sm text-foreground-muted">No results</p>}
          {results.map((result) => (
            <button
              key={result.conversation.id}
              type="button"
              onClick={() => onSelect(result.conversation.id)}
              className="block w-full px-3 py-2 text-left text-sm hover:bg-accent-soft"
            >
              <p className="font-medium text-foreground">{result.conversation.title}</p>
              {result.highlighted_snippet && (
                <p
                  className="mt-0.5 truncate text-xs text-foreground-muted [&_mark]:bg-accent-soft [&_mark]:text-accent-hover"
                  dangerouslySetInnerHTML={{ __html: result.highlighted_snippet }}
                />
              )}
            </button>
          ))}
        </div>
      )}
    </div>
  );
}
