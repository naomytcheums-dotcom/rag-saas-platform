"use client";

// Phase 5, Étape 15 -- applies the current organization's real branding
// as CSS custom properties on `:root`, reusing the SAME variable names
// app/globals.css already defines (`--accent`, `--accent-hover`,
// `--accent-soft`, `--font-sans`) rather than inventing a parallel set
// no component actually reads. Deliberately does NOT touch
// `--background`/`--foreground`/`--surface` -- OrganizationBranding has
// no such fields (only primary/secondary/accent/font), and this
// app's own globals.css carries a standing, explicit constraint
// ("light-only, elegant theme... NEVER dark mode") that a real base
// theme override could violate; branding only ever customizes accent
// color/logo/favicon/font, never the light/dark foundation.
//
// `--accent-hover`/`--accent-soft` are fixed hex values in
// globals.css, not derived from `--accent` -- overriding only
// `--accent` would leave a mismatched hover/soft state the moment an
// organization's own primary_color differs from the platform default.
// `lib/branding-colors.ts` derives real, consistent shades instead.

import { useEffect } from "react";
import { darken, lighten } from "@/lib/branding-colors";
import { useBranding } from "@/lib/branding-context";

const CUSTOM_CSS_STYLE_ID = "org-branding-custom-css";
const FAVICON_LINK_SELECTOR = "link[rel*='icon']";

export function BrandingApplier() {
  const { branding } = useBranding();

  useEffect(() => {
    const root = document.documentElement.style;

    root.setProperty("--accent", branding.primary_color);
    root.setProperty("--accent-hover", darken(branding.primary_color, 0.12));
    root.setProperty("--accent-soft", lighten(branding.primary_color, 0.85));
    root.setProperty("--accent-soft-hover", lighten(branding.primary_color, 0.75));
    root.setProperty("--org-secondary-color", branding.secondary_color);

    if (branding.font_family) {
      root.setProperty("--font-sans", branding.font_family);
    }
  }, [branding.primary_color, branding.secondary_color, branding.font_family]);

  useEffect(() => {
    if (!branding.favicon_url) return;
    const existing = document.querySelector<HTMLLinkElement>(FAVICON_LINK_SELECTOR);
    if (existing) {
      existing.href = branding.favicon_url;
    } else {
      const link = document.createElement("link");
      link.rel = "icon";
      link.href = branding.favicon_url;
      document.head.appendChild(link);
    }
  }, [branding.favicon_url]);

  useEffect(() => {
    // Real, deliberate trust boundary: `custom_css` reaching this
    // component already passed `api/security/organization_branding.py`'s
    // own `validate_custom_css` at write time (denylist of
    // javascript:/expression()/@import — see ROADMAP.md's own tracked
    // P2 for the one known gap in that denylist, external url()).
    // Injected the same way the widget's own inline <style> already
    // does for its per-org CSS variables — not a new trust boundary.
    let style = document.getElementById(CUSTOM_CSS_STYLE_ID);
    if (!branding.custom_css) {
      style?.remove();
      return;
    }
    if (!style) {
      style = document.createElement("style");
      style.id = CUSTOM_CSS_STYLE_ID;
      document.head.appendChild(style);
    }
    style.textContent = branding.custom_css;
  }, [branding.custom_css]);

  return null;
}
