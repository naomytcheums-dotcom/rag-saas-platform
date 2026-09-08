"use client";

import { useEffect, useState } from "react";
import { api } from "@/lib/api";

interface SuggestedQuestionsProps {
  organizationId: string;
  onSelect: (question: string) => void;
}

// Partie 8.1.17 -- GET /organizations/{org_id}/suggested-questions,
// rendered as clickable chips that send the question straight to chat.
export default function SuggestedQuestions({ organizationId, onSelect }: SuggestedQuestionsProps) {
  const [questions, setQuestions] = useState<string[]>([]);

  useEffect(() => {
    void api
      .get<{ questions: string[] }>(`/organizations/${organizationId}/suggested-questions`)
      .then((data) => setQuestions(data.questions))
      .catch(() => setQuestions([]));
  }, [organizationId]);

  if (questions.length === 0) return null;

  return (
    <div className="flex flex-wrap gap-2">
      {questions.map((question) => (
        <button
          key={question}
          type="button"
          onClick={() => onSelect(question)}
          className="rounded-full border border-border-strong bg-surface px-3 py-1.5 text-sm text-foreground hover:border-accent hover:bg-accent-soft"
        >
          {question}
        </button>
      ))}
    </div>
  );
}
