"use client";

import { useState } from "react";
import { useTranslation } from "@/lib/i18n";
import type { Citation as CitationType } from "@/lib/types";
import CitationModal from "./CitationModal";

interface CitationListProps {
  citations: CitationType[];
}

// Partie 8.1.4 -- every citation for one response, listed together
// (not just inline) so a user can scan sources without re-reading the
// answer, and jump between them.
export default function CitationList({ citations }: CitationListProps) {
  const { t } = useTranslation();
  const [active, setActive] = useState<CitationType | null>(null);

  if (citations.length === 0) return null;

  return (
    <div className="mt-3 border-t border-border pt-3">
      <h3 className="mb-2 text-xs font-semibold uppercase tracking-wide text-foreground-muted">
        {t("sources", { count: citations.length })}
      </h3>
      <ul className="space-y-1.5">
        {citations.map((citation) => (
          <li key={citation.id}>
            <button
              type="button"
              onClick={() => setActive(citation)}
              className="flex w-full items-center gap-2 rounded-lg px-2 py-1.5 text-left text-sm hover:bg-accent-soft"
            >
              <span className="flex h-5 w-5 shrink-0 items-center justify-center rounded-full bg-accent-soft text-xs font-semibold text-accent-hover">
                {citation.citation_number}
              </span>
              <span className="truncate text-foreground">{citation.document_title ?? t("untitled_document")}</span>
              {citation.page != null && <span className="shrink-0 text-xs text-foreground-muted">p.{citation.page}</span>}
            </button>
          </li>
        ))}
      </ul>

      {active && <CitationModal citation={active} onClose={() => setActive(null)} />}
    </div>
  );
}
