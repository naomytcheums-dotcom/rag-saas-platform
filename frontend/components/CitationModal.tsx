"use client";

import { useEffect, useRef } from "react";
import { createPortal } from "react-dom";
import type { Citation } from "@/lib/types";

interface CitationModalProps {
  citation: Citation;
  onClose: () => void;
}

// Partie 8.1.4 -- full citation detail: complete passage with context,
// source document/page/URL. Closes on Escape or backdrop click, and
// traps initial focus for keyboard/screen-reader users.
//
// Rendered via a portal into document.body: <Citation> (and this
// modal along with it) can appear inline inside a real response's own
// <p> text -- HTML forbids block content (a fixed-position <div> with
// <h2>/<blockquote>/<dl> children) inside a <p>, which produced a
// real hydration error when this modal rendered as a normal child
// instead. A portal keeps the DOM position valid regardless of where
// <Citation> is used, while React's own event bubbling still works
// exactly as if it were nested there.
export default function CitationModal({ citation, onClose }: CitationModalProps) {
  const closeButtonRef = useRef<HTMLButtonElement>(null);

  useEffect(() => {
    closeButtonRef.current?.focus();
    const onKeyDown = (event: KeyboardEvent) => {
      if (event.key === "Escape") onClose();
    };
    window.addEventListener("keydown", onKeyDown);
    return () => window.removeEventListener("keydown", onKeyDown);
  }, [onClose]);

  return createPortal(
    <div
      className="fixed inset-0 z-50 flex items-center justify-center bg-black/20 p-4"
      onClick={onClose}
      role="presentation"
    >
      <div
        role="dialog"
        aria-modal="true"
        aria-labelledby="citation-modal-title"
        onClick={(event) => event.stopPropagation()}
        className="w-full max-w-lg rounded-2xl border border-border bg-surface p-6 shadow-md"
      >
        <div className="mb-4 flex items-start justify-between gap-4">
          <h2 id="citation-modal-title" className="text-lg font-semibold text-foreground">
            Citation [{citation.citation_number}]
          </h2>
          <button
            ref={closeButtonRef}
            onClick={onClose}
            aria-label="Close"
            className="rounded-full p-1 text-foreground-muted hover:bg-accent-soft hover:text-accent-hover"
          >
            ✕
          </button>
        </div>

        <blockquote className="mb-4 rounded-lg bg-surface-muted p-4 text-sm text-foreground">
          {citation.exact_passage}
        </blockquote>

        <dl className="space-y-2 text-sm">
          <div className="flex justify-between gap-4">
            <dt className="text-foreground-muted">Document</dt>
            <dd className="text-right font-medium text-foreground">{citation.document_title ?? "Untitled document"}</dd>
          </div>
          {citation.page != null && (
            <div className="flex justify-between gap-4">
              <dt className="text-foreground-muted">Page</dt>
              <dd className="text-foreground">{citation.page}</dd>
            </div>
          )}
          {citation.relevance_label && (
            <div className="flex justify-between gap-4">
              <dt className="text-foreground-muted">Relevance</dt>
              <dd className="text-foreground">{citation.relevance_label}</dd>
            </div>
          )}
        </dl>

        {citation.url && (
          <a
            href={citation.url}
            target="_blank"
            rel="noreferrer"
            className="mt-4 inline-block rounded-lg bg-accent px-4 py-2 text-sm font-medium text-white hover:bg-accent-hover"
          >
            Open source
          </a>
        )}
      </div>
    </div>,
    document.body,
  );
}
