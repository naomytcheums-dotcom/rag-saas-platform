"use client";

import { useEffect, useState } from "react";

const STORAGE_KEY = "cookie_consent_ack";

// Built via audit (2026-09-19). Real, honest context: this app sets
// only 2 cookies today, both strictly necessary/functional (the UI
// language preference, api/routers/i18n.py, and the httpOnly refresh
// token, api/routers/auth.py) -- no analytics/advertising script exists
// anywhere in this frontend (grepped, zero matches for gtag/GA/fbq).
// Under GDPR/ePrivacy, strictly necessary cookies do not legally
// require a consent banner. This component exists for completeness and
// transparency anyway (a visitor can see plainly what's stored and
// why), not because it was a compliance gap -- see docs/compliance/COOKIES.md.
//
// Real bug found and fixed live (2026-09-19): reading localStorage in
// the useState lazy initializer made the server's render (window
// undefined, always "acknowledged") disagree with the client's very
// first hydration pass (real localStorage, usually "not acknowledged")
// -- a real hydration mismatch (React error #418), reproduced live on
// production and confirmed via a hard reload. Starting at `false` on
// every render (server AND the client's first pass) and only checking
// localStorage in an effect (client-only, after hydration) keeps that
// first render identical everywhere; the one-render delay before the
// banner can appear is the correct, standard trade-off for this exact
// "read a browser-only API after mount" case.
export default function CookieBanner() {
  const [visible, setVisible] = useState(false);

  useEffect(() => {
    try {
      // eslint-disable-next-line react-hooks/set-state-in-effect -- justified: syncing with a real external system (localStorage) after mount, not a value derivable from props/state.
      if (!window.localStorage.getItem(STORAGE_KEY)) setVisible(true);
    } catch {
      // localStorage unavailable (private mode, blocked) -- fail open, never crash the page over this.
    }
  }, []);

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
