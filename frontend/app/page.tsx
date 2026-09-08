"use client";

import Citation from "@/components/Citation";
import CitationList from "@/components/CitationList";
import CopyButton from "@/components/CopyButton";
import FeedbackButtons from "@/components/FeedbackButtons";
import LanguageSwitcher from "@/components/LanguageSwitcher";
import type { Citation as CitationType } from "@/lib/types";

const MOCK_CITATIONS: CitationType[] = [
  {
    id: "c1",
    citation_number: 1,
    document_id: "d1",
    document_title: "RAG Architecture Guide",
    page: 4,
    url: "https://example.com/rag-guide",
    exact_passage: "Retrieval-augmented generation combines a retriever over a document store with a generative language model.",
    relevance_label: "High",
    relevance_score: 0.92,
  },
  {
    id: "c2",
    citation_number: 2,
    document_id: "d2",
    document_title: "Chunking Strategies",
    page: 12,
    exact_passage: "Semantic chunking groups sentences by topical similarity rather than a fixed token count.",
    relevance_label: "Medium",
    relevance_score: 0.71,
  },
];

const MOCK_ANSWER =
  "RAG systems combine retrieval with generation to ground answers in real documents. Chunking strategy strongly affects retrieval quality.";

// A real, minimal showcase of the Partie 8.1 chat components, wired
// against mock data (no live conversation exists yet without an
// authenticated session/chat flow, still to come) -- lets the light,
// orange-and-white theme and every component's real interaction be
// verified visually before the full chat page is built on top of it.
export default function Home() {
  return (
    <main className="mx-auto flex min-h-screen w-full max-w-2xl flex-col gap-8 px-6 py-10">
      <header className="flex items-center justify-between">
        <h1 className="text-xl font-semibold text-foreground">RAG SaaS Platform</h1>
        <LanguageSwitcher />
      </header>

      <section className="rounded-2xl border border-border bg-surface p-5 shadow-sm">
        <p className="text-xs font-semibold uppercase tracking-wide text-accent-hover">Assistant</p>
        <p className="mt-2 text-sm leading-relaxed text-foreground">
          RAG systems combine retrieval with generation to ground answers in real documents
          <Citation citation={MOCK_CITATIONS[0]} />. Chunking strategy strongly affects retrieval
          quality
          <Citation citation={MOCK_CITATIONS[1]} />.
        </p>

        <div className="mt-3 flex items-center gap-1">
          <CopyButton text={MOCK_ANSWER} citations={MOCK_CITATIONS} format="with_citations" />
          <FeedbackButtons messageId="mock-message-id" />
        </div>

        <CitationList citations={MOCK_CITATIONS} />
      </section>

      <section>
        <h2 className="mb-2 text-xs font-semibold uppercase tracking-wide text-foreground-muted">
          Suggested questions
        </h2>
        <div className="flex flex-wrap gap-2">
          <span className="rounded-full border border-border-strong bg-surface px-3 py-1.5 text-sm text-foreground">
            What is retrieval-augmented generation?
          </span>
          <span className="rounded-full border border-border-strong bg-surface px-3 py-1.5 text-sm text-foreground">
            How does semantic chunking work?
          </span>
        </div>
      </section>
    </main>
  );
}
