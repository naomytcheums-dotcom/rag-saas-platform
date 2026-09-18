"use client";

import { useEffect, useRef, useState } from "react";
import ChatComposer from "@/components/ChatComposer";
import ChatSidebar from "@/components/ChatSidebar";
import MessageBubble from "@/components/MessageBubble";
import { useTranslation } from "@/lib/i18n";
import { useCurrentOrg } from "@/lib/useCurrentOrg";
import { useRealChat } from "@/lib/useRealChat";

const STARTER_QUESTIONS = ["What is retrieval-augmented generation?", "How does semantic chunking work?", "Which retriever should I use?"];

// The full, real, responsive chat interface -- every Partie 8.1/8.2
// component assembled into one real page: sidebar (conversations,
// search), message thread (citations, copy, feedback, regenerate,
// voice playback), and a composer (text + voice input, tap or
// push-to-talk). Real bug fixed (2026-09-18), found via a live manual
// test: the conversation thread used to run on local mock state
// (lib/mockChat.ts) with a comment claiming login wasn't wired up yet
// -- stale by the time of that test, since login already worked. Now
// wired to the real backend (lib/useRealChat.ts): POST /chat/stream,
// a real agent, and a real, persisted conversation.
export default function Home() {
  const { t } = useTranslation();
  const { org, loading: orgLoading } = useCurrentOrg();
  const { messages, pending, error, sendMessage, editMessage, regenerate } = useRealChat(org?.id ?? "");
  const [draft, setDraft] = useState("");
  const [sidebarOpen, setSidebarOpen] = useState(false);
  const scrollRef = useRef<HTMLDivElement>(null);

  if (orgLoading || !org) {
    return <div className="flex h-screen items-center justify-center text-sm text-foreground-muted">Chargement…</div>;
  }

  useEffect(() => {
    scrollRef.current?.scrollTo({ top: scrollRef.current.scrollHeight, behavior: "smooth" });
  }, [messages.length]);

  const lastAssistantId = [...messages].reverse().find((m) => m.role === "assistant")?.id;

  return (
    <div className="flex h-screen overflow-hidden">
      <ChatSidebar open={sidebarOpen} onClose={() => setSidebarOpen(false)} />

      <div className="flex min-w-0 flex-1 flex-col">
        <header className="flex items-center justify-between border-b border-border bg-surface px-4 py-3 sm:px-6">
          <div className="flex items-center gap-2">
            <button
              type="button"
              onClick={() => setSidebarOpen(true)}
              aria-label={t("open_conversations")}
              className="rounded-lg p-1.5 text-foreground-muted hover:bg-surface-muted md:hidden"
            >
              ☰
            </button>
            <h1 className="text-base font-semibold text-foreground sm:text-lg">RAG SaaS Platform</h1>
          </div>
        </header>

        <main ref={scrollRef} className="flex-1 space-y-4 overflow-y-auto px-4 py-6 sm:px-6">
          <div className="mx-auto flex max-w-3xl flex-col gap-4">
            {error && <p className="rounded-lg bg-danger-soft px-3 py-2 text-sm text-danger">{error}</p>}

            {messages.map((message) => (
              <MessageBubble
                key={message.id}
                message={message}
                isLast={message.id === lastAssistantId}
                onEdit={editMessage}
                onRegenerate={regenerate}
                regenerating={pending && message.id === lastAssistantId}
              />
            ))}

            {pending && (
              <div className="flex justify-start">
                <div className="rounded-2xl rounded-tl-sm border border-border bg-surface px-4 py-3 text-sm text-foreground-muted">
                  <span className="inline-flex gap-1">
                    <span className="h-1.5 w-1.5 animate-bounce rounded-full bg-border-strong [animation-delay:-0.3s]" />
                    <span className="h-1.5 w-1.5 animate-bounce rounded-full bg-border-strong [animation-delay:-0.15s]" />
                    <span className="h-1.5 w-1.5 animate-bounce rounded-full bg-border-strong" />
                  </span>
                </div>
              </div>
            )}

            {messages.length <= 2 && (
              <div>
                <h2 className="mb-2 text-xs font-semibold uppercase tracking-wide text-foreground-muted">{t("suggested_questions")}</h2>
                <div className="flex flex-wrap gap-2">
                  {STARTER_QUESTIONS.map((question) => (
                    <button
                      key={question}
                      type="button"
                      onClick={() => sendMessage(question)}
                      className="rounded-full border border-border-strong bg-surface px-3 py-1.5 text-sm text-foreground hover:border-accent hover:bg-accent-soft"
                    >
                      {question}
                    </button>
                  ))}
                </div>
              </div>
            )}
          </div>
        </main>

        <ChatComposer value={draft} onChange={setDraft} onSend={sendMessage} disabled={pending} />
      </div>
    </div>
  );
}
