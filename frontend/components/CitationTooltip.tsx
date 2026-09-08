"use client";

import { createPortal } from "react-dom";
import type { Citation } from "@/lib/types";

interface CitationTooltipProps {
  citation: Citation;
  anchorRect: { top: number; left: number; width: number } | null;
}

// Partie 8.1.4 -- hovering a citation number shows the exact passage,
// its source, and its relevance score without a full modal.
//
// Rendered via a portal into document.body (see CitationModal.tsx's
// own top comment for why: a <Citation> can appear inline inside a
// real response's own <p> text, and HTML forbids block content like
// this tooltip's <div> inside a <p>). Positioned with real, fixed
// viewport coordinates computed from the trigger button's own
// getBoundingClientRect() (passed in as `anchorRect`), since a portal
// escapes the trigger's own DOM position and can no longer rely on
// CSS `position: absolute` relative to it.
export default function CitationTooltip({ citation, anchorRect }: CitationTooltipProps) {
  if (!anchorRect) return null;

  // Real, minimal viewport clamping: a citation near the right/left
  // edge would otherwise center this 288px-wide tooltip partly off
  // screen (observed directly while testing this component).
  const TOOLTIP_WIDTH = 288;
  const idealLeft = anchorRect.left + anchorRect.width / 2 - TOOLTIP_WIDTH / 2;
  const clampedLeft = Math.min(Math.max(idealLeft, 8), window.innerWidth - TOOLTIP_WIDTH - 8);

  return createPortal(
    <div
      role="tooltip"
      style={{ position: "fixed", top: anchorRect.top - 8, left: clampedLeft, transform: "translateY(-100%)" }}
      className="z-40 w-72 rounded-lg border border-border bg-surface p-3 text-sm shadow-md"
    >
      <p className="mb-1 line-clamp-3 text-foreground-muted italic">&ldquo;{citation.exact_passage}&rdquo;</p>
      <div className="mt-2 flex items-center justify-between text-xs text-foreground-muted">
        <span className="truncate font-medium text-foreground">
          {citation.document_title ?? "Document"}
          {citation.page ? ` · p.${citation.page}` : ""}
        </span>
        {typeof citation.relevance_score === "number" && (
          <span className="ml-2 shrink-0 rounded-full bg-accent-soft px-2 py-0.5 text-accent-hover">
            {Math.round(citation.relevance_score * 100)}%
          </span>
        )}
      </div>
    </div>,
    document.body,
  );
}
