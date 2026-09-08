"use client";

import { useState } from "react";
import type { Citation, ConversationMessage } from "@/lib/types";

// Real, local, client-only mock conversation state -- this frontend
// has no real login/session flow wired up yet (a separate, real,
// future piece of work), so there is no real backend conversation to
// drive this page's own demo against. Every component this page
// composes is already wired against the REAL backend API built across
// Partie 8.1/8.2 (frontend/lib/api.ts) -- this mock layer only stands
// in for "a real conversation already exists", so the full page layout
// and every component's real interaction can be demonstrated end to
// end today, without pretending a fake network call is a real one.
export interface MockMessage extends Pick<ConversationMessage, "id" | "role" | "content" | "created_at"> {
  citations?: Citation[];
}

const MOCK_CITATIONS: Citation[] = [
  {
    id: "c1", citation_number: 1, document_id: "d1", document_title: "RAG Architecture Guide", page: 4,
    url: "https://en.wikipedia.org/wiki/Retrieval-augmented_generation",
    exact_passage: "Retrieval-augmented generation combines a retriever over a document store with a generative language model.",
    relevance_label: "High", relevance_score: 0.92,
  },
  {
    id: "c2", citation_number: 2, document_id: "d2", document_title: "Chunking Strategies", page: 12,
    url: "https://en.wikipedia.org/wiki/Semantic_search",
    exact_passage: "Semantic chunking groups sentences by topical similarity rather than a fixed token count.",
    relevance_label: "Medium", relevance_score: 0.71,
  },
];

function nowIso(): string {
  return new Date().toISOString();
}

const INITIAL_MESSAGES: MockMessage[] = [
  { id: "m1", role: "user", content: "What is RAG and how does chunking affect it?", created_at: nowIso() },
  {
    id: "m2", role: "assistant",
    content: "RAG systems combine retrieval with generation to ground answers in real documents [1]. Chunking strategy strongly affects retrieval quality [2].",
    citations: MOCK_CITATIONS, created_at: nowIso(),
  },
];

const CANNED_REPLIES = [
  "That's a great follow-up. Based on the indexed documents, the key factor is how chunk boundaries preserve semantic meaning.",
  "Here's a more detailed answer, grounded in the same sources as before.",
  "I looked into that further -- the short answer is it depends on your retrieval strategy (hybrid, vector-only, or BM25-only).",
];

export function useMockChat() {
  const [messages, setMessages] = useState<MockMessage[]>(INITIAL_MESSAGES);
  const [pending, setPending] = useState(false);

  function sendMessage(text: string) {
    if (!text.trim()) return;
    const userMessage: MockMessage = { id: crypto.randomUUID(), role: "user", content: text, created_at: nowIso() };
    setMessages((prev) => [...prev, userMessage]);
    setPending(true);
    setTimeout(() => {
      const reply = CANNED_REPLIES[Math.floor(Math.random() * CANNED_REPLIES.length)];
      setMessages((prev) => [...prev, { id: crypto.randomUUID(), role: "assistant", content: reply, created_at: nowIso() }]);
      setPending(false);
    }, 600);
  }

  function editMessage(id: string, newContent: string) {
    setMessages((prev) => prev.map((m) => (m.id === id ? { ...m, content: newContent } : m)));
    setPending(true);
    setTimeout(() => {
      const reply = CANNED_REPLIES[Math.floor(Math.random() * CANNED_REPLIES.length)];
      setMessages((prev) => [...prev, { id: crypto.randomUUID(), role: "assistant", content: reply, created_at: nowIso() }]);
      setPending(false);
    }, 600);
  }

  function regenerate(id: string) {
    setPending(true);
    setTimeout(() => {
      const reply = CANNED_REPLIES[Math.floor(Math.random() * CANNED_REPLIES.length)];
      setMessages((prev) => prev.map((m) => (m.id === id ? { ...m, content: reply, created_at: nowIso() } : m)));
      setPending(false);
    }, 500);
  }

  return { messages, pending, sendMessage, editMessage, regenerate };
}
