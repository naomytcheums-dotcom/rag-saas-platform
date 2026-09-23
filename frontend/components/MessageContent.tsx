"use client";

import type { Citation as CitationType } from "@/lib/types";
import ChatMarkdown from "./ChatMarkdown";

interface MessageContentProps {
  text: string;
  citations?: CitationType[];
}

// Phase 5, Étape 9 -- real Markdown + syntax-highlighted rendering
// (ChatMarkdown.tsx), replacing this component's own previous plain
// "[n]" citation substitution over raw text. The real citation
// click-through behavior (Partie 8.1.4) is preserved exactly --
// ChatMarkdown's own `a` renderer intercepts `citation:n` links and
// swaps in the same real, clickable <Citation> badge.
export default function MessageContent({ text, citations = [] }: MessageContentProps) {
  return <ChatMarkdown text={text} citations={citations} />;
}
