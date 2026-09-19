"use client";

import { useState } from "react";

const STORAGE_KEY = "cookie_consent_ack";

function hasAcknowledged(): boolean {
  if (typeof window === "undefined") return true;
  try {
    return Boolean(window.localStorage.getItem(STORAGE_KEY));
  } catch {
    return false;
  }
}

// Built via audit (2026-09-19). Real, honest context: this app sets
// only 2 cookies today, both strictly necessary/functional (the UI
// language preference, api/routers/i18n.py, and the httpOnly refresh
// token, api/routers/auth.py) -- no analytics/advertising script exists
// anywhere in this frontend (grepped, zero matches for gtag/GA/fbq).
// Under GDPR/ePrivacy, strictly necessary cookies do not legally
// require a consent banner. This component exists for completeness and
// transparency anyway (a visitor can see plainly what's stored and
// why), not because it was a compliance gap -- see docs/compliance/COOKIES.md.
export default function CookieBanner() {
  const [visible, setVisible] = useState(() => !hasAcknowledged());

  const dismiss = () => {
    setVisible(false);
    try {
      window.localStorage.setItem(STORAGE_KEY, "1");
    } catch {
      // Same fail-open reasoning as above.
    }
  };

  if (!visible) return null;

  return (
    <div className="fixed inset-x-0 bottom-0 z-50 flex flex-col gap-2 border-t border-border bg-surface px-4 py-3 text-sm text-foreground shadow-md sm:flex-row sm:items-center sm:justify-between">
      <p className="text-foreground-muted">
        Ce site utilise uniquement des cookies strictement necessaires (preference de langue, session
        de connexion) -- aucun cookie publicitaire ou de suivi.
      </p>
      <button
        type="button"
        onClick={dismiss}
        className="shrink-0 rounded-lg bg-accent px-3 py-1.5 text-sm font-medium text-white hover:bg-accent-hover"
      >
        Compris
      </button>
    </div>
  );
}
