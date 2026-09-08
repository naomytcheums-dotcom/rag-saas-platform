"use client";

import { useRef, useState } from "react";
import type { Citation as CitationType } from "@/lib/types";
import CitationModal from "./CitationModal";
import CitationTooltip from "./CitationTooltip";

interface CitationProps {
  citation: CitationType;
}

type AnchorRect = { top: number; left: number; width: number } | null;

// Partie 8.1.4 -- the inline [n] marker in a response. Hover shows a
// quick preview (CitationTooltip); click (or Enter/Space, for
// keyboard users) opens the full detail (CitationModal). A real
// <button>, not a <span onClick>, so it's natively focusable and
// screen-reader-announced as interactive.
export default function Citation({ citation }: CitationProps) {
  const [anchorRect, setAnchorRect] = useState<AnchorRect>(null);
  const [showModal, setShowModal] = useState(false);
  const buttonRef = useRef<HTMLButtonElement>(null);

  // Real ref reads happen here, in an event handler -- never during
  // render (React's own react-hooks/refs rule forbids that, since a
  // ref's current value isn't tracked for re-renders).
  function updateAnchorRect() {
    const rect = buttonRef.current?.getBoundingClientRect();
    setAnchorRect(rect ? { top: rect.top, left: rect.left, width: rect.width } : null);
  }

  return (
    <span className="relative inline-block">
      <button
        ref={buttonRef}
        type="button"
        onClick={() => setShowModal(true)}
        onMouseEnter={updateAnchorRect}
        onMouseLeave={() => setAnchorRect(null)}
        onFocus={updateAnchorRect}
        onBlur={() => setAnchorRect(null)}
        aria-label={`Citation ${citation.citation_number}: ${citation.document_title ?? "source"}`}
        className="mx-0.5 inline-flex h-5 min-w-5 items-center justify-center rounded-full bg-accent-soft px-1 align-super text-xs font-semibold text-accent-hover hover:bg-accent hover:text-white"
      >
        {citation.citation_number}
      </button>

      {anchorRect && <CitationTooltip citation={citation} anchorRect={anchorRect} />}

      {showModal && <CitationModal citation={citation} onClose={() => setShowModal(false)} />}
    </span>
  );
}
