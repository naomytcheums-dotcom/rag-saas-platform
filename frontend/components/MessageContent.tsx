"use client";

import type { Citation as CitationType } from "@/lib/types";
import Citation from "./Citation";

interface MessageContentProps {
  text: string;
  citations?: CitationType[];
}

// Real, shared renderer: splits an assistant answer's own real "[n]"
// citation markers and swaps each one for a real, clickable <Citation>
// badge (Partie 8.1.4) -- the one real place this string -> component
// substitution happens, so every real message in the app (mock demo
// data today, a real backend response tomorrow) renders citations
// identically.
export default function MessageContent({ text, citations = [] }: MessageContentProps) {
  const byNumber = new Map(citations.map((c) => [c.citation_number, c]));
  const parts: React.ReactNode[] = [];
  let lastIndex = 0;
  let match: RegExpExecArray | null;

  // A fresh RegExp per render (not a real, shared module-level one) --
  // React's own compiler forbids mutating an external object's state
  // (a regex's own real `lastIndex`) during render.
  const citationToken = /\[(\d+)\]/g;
  while ((match = citationToken.exec(text))) {
    if (match.index > lastIndex) parts.push(text.slice(lastIndex, match.index));
    const citation = byNumber.get(Number(match[1]));
    parts.push(citation ? <Citation key={`${citation.id}-${match.index}`} citation={citation} /> : match[0]);
    lastIndex = match.index + match[0].length;
  }
  if (lastIndex < text.length) parts.push(text.slice(lastIndex));

  return <p className="text-sm leading-relaxed text-foreground">{parts}</p>;
}
