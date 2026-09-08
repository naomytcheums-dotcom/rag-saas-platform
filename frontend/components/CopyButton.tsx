"use client";

import { useState } from "react";
import type { Citation } from "@/lib/types";

interface CopyButtonProps {
  text: string;
  citations?: Citation[];
  format?: "plain" | "markdown" | "with_citations";
}

// Partie 8.1.5 -- copies the response to the clipboard, with a real
// visual "Copied!" confirmation and a real, honest failure state when
// the Clipboard API isn't available (e.g. an insecure/non-HTTPS
// context) instead of silently doing nothing.
export default function CopyButton({ text, citations = [], format = "plain" }: CopyButtonProps) {
  const [state, setState] = useState<"idle" | "copied" | "error">("idle");

  function buildContent(): string {
    if (format === "with_citations" && citations.length > 0) {
      const sources = citations
        .map((c) => `[${c.citation_number}] ${c.document_title ?? "Untitled document"}${c.url ? ` — ${c.url}` : ""}`)
        .join("\n");
      return `${text}\n\nSources:\n${sources}`;
    }
    if (format === "markdown") return text;
    return text;
  }

  async function handleCopy() {
    const content = buildContent();
    try {
      if (!navigator.clipboard) throw new Error("Clipboard API unavailable");
      await navigator.clipboard.writeText(content);
      setState("copied");
    } catch {
      setState("error");
    }
    setTimeout(() => setState("idle"), 2000);
  }

  return (
    <button
      type="button"
      onClick={handleCopy}
      aria-label="Copy response"
      className="inline-flex items-center gap-1.5 rounded-lg px-2 py-1 text-xs font-medium text-foreground-muted hover:bg-accent-soft hover:text-accent-hover"
    >
      {state === "copied" ? "Copied!" : state === "error" ? "Couldn't copy" : "Copy"}
    </button>
  );
}
