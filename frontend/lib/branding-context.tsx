"use client";

// Phase 5, Étape 15 -- applies an organization's own real branding
// (`OrganizationBranding`, Partie 1.3.10/19) across the dashboard's
// global UI, not just the isolated admin preview card
// (components/whitelabel/PreviewBranding.tsx) or the embeddable widget
// (its own, deliberately separate WidgetConfig colors -- see
// ROADMAP.md's own entry for why those two stay unlinked).
//
// Reuses the REAL, already-existing `WhiteLabelConfig` type and
// `getWhiteLabelConfig` call (lib/services/whitelabel.ts,
// GET /organizations/{org_id}/whitelabel/config) rather than declaring
// a second, parallel `Branding` interface and endpoint the way this
// étape's own spec pseudocode illustrated -- that endpoint and type
// already exist for real.

import { createContext, useCallback, useContext, useEffect, useState } from "react";
import * as whitelabelService from "@/lib/services/whitelabel";
import type { WhiteLabelConfig } from "@/lib/services/whitelabel";
import { useCurrentOrg } from "@/lib/useCurrentOrg";

// Real defaults: this platform's own base theme (app/globals.css) --
// an organization with no branding row overrides yet (or still
// loading) sees the platform's own real colors, never an arbitrary
// placeholder color.
const DEFAULT_BRANDING: Pick<WhiteLabelConfig, "logo_url" | "favicon_url" | "primary_color" | "secondary_color" | "accent_color" | "font_family" | "custom_css" | "brand_name"> = {
  logo_url: null,
  favicon_url: null,
  primary_color: "#f5842a",
  secondary_color: "#241c14",
  accent_color: "#f5842a",
  font_family: "Inter",
  custom_css: null,
  brand_name: null,
};

interface BrandingContextValue {
  branding: typeof DEFAULT_BRANDING;
  loading: boolean;
  refresh: () => Promise<void>;
}

const BrandingContext = createContext<BrandingContextValue>({
  branding: DEFAULT_BRANDING,
  loading: true,
  refresh: async () => {},
});

export function BrandingProvider({ children }: { children: React.ReactNode }) {
  const { org } = useCurrentOrg();
  const [branding, setBranding] = useState(DEFAULT_BRANDING);
  const [loading, setLoading] = useState(true);

  const refresh = useCallback(async () => {
    if (!org) return;
    try {
      const config = await whitelabelService.getWhiteLabelConfig(org.id);
      setBranding(config);
    } catch {
      // Real, deliberate fail-open: a branding fetch failure must never
      // block the dashboard from rendering -- same "degrade, don't
      // break" reasoning as api/services/cache_service.py. The platform's
      // own default colors stay applied.
      setBranding(DEFAULT_BRANDING);
    } finally {
      setLoading(false);
    }
  }, [org]);

  useEffect(() => {
    // eslint-disable-next-line react-hooks/set-state-in-effect -- syncing with the backend after mount/org change
    void refresh();
  }, [refresh]);

  return (
    <BrandingContext.Provider value={{ branding, loading, refresh }}>
      {children}
    </BrandingContext.Provider>
  );
}

export function useBranding() {
  return useContext(BrandingContext);
}
