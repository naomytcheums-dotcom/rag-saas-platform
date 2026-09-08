"use client";

import { useEffect, useState } from "react";
import { api } from "@/lib/api";
import type { FollowUpQuestion } from "@/lib/types";

interface FollowUpQuestionsProps {
  messageId: string;
  onSelect: (question: string) => void;
}

// Partie 8.1.18 -- generates (POST) then displays follow-up questions
// for one assistant answer, as clickable chips; marks a question
// clicked (real, persisted analytics signal) when chosen.
export default function FollowUpQuestions({ messageId, onSelect }: FollowUpQuestionsProps) {
  const [questions, setQuestions] = useState<FollowUpQuestion[]>([]);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    let cancelled = false;
    (async () => {
      try {
        const existing = await api.get<FollowUpQuestion[]>(`/messages/${messageId}/follow-up`);
        if (cancelled) return;
        if (existing.length > 0) {
          setQuestions(existing);
        } else {
          const generated = await api.post<FollowUpQuestion[]>(`/messages/${messageId}/follow-up`, {});
          if (!cancelled) setQuestions(generated);
        }
      } catch {
        if (!cancelled) setQuestions([]);
      } finally {
        if (!cancelled) setLoading(false);
      }
    })();
    return () => {
      cancelled = true;
    };
  }, [messageId]);

  if (loading || questions.length === 0) return null;

  return (
    <div className="mt-2 flex flex-wrap gap-2">
      {questions.map((question) => (
        <button
          key={question.id}
          type="button"
          onClick={() => onSelect(question.question)}
          className="rounded-full border border-border bg-surface-muted px-3 py-1 text-xs text-foreground-muted hover:border-accent hover:text-accent-hover"
        >
          {question.question}
        </button>
      ))}
    </div>
  );
}
