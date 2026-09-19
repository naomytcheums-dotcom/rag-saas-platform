"use client";

import { useEffect, useState } from "react";
import { ColorPicker } from "@/components/whitelabel/ColorPicker";
import { CustomCSSEditor } from "@/components/whitelabel/CustomCSSEditor";
import { CustomJSEditor } from "@/components/whitelabel/CustomJSEditor";
import type { WhiteLabelConfig as WhiteLabelConfigType } from "@/lib/services/whitelabel";

interface WhiteLabelConfigProps {
  config: WhiteLabelConfigType;
  onSave: (data: Partial<WhiteLabelConfigType>) => Promise<unknown>;
}

export function WhiteLabelConfig({ config, onSave }: WhiteLabelConfigProps) {
  const [brandName, setBrandName] = useState(config.brand_name ?? "");
  const [primaryColor, setPrimaryColor] = useState(config.primary_color);
  const [secondaryColor, setSecondaryColor] = useState(config.secondary_color);
  const [accentColor, setAccentColor] = useState(config.accent_color);
  const [companyEmail, setCompanyEmail] = useState(config.company_email ?? "");
  const [supportEmail, setSupportEmail] = useState(config.support_email ?? "");
  const [customCss, setCustomCss] = useState(config.custom_css ?? "");
  const [customJs, setCustomJs] = useState(config.custom_js ?? "");
  const [hideBranding, setHideBranding] = useState(config.hide_platform_branding);
  const [isActive, setIsActive] = useState(config.is_active);
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [saved, setSaved] = useState(false);

  useEffect(() => {
    // eslint-disable-next-line react-hooks/set-state-in-effect -- justified: syncing with a real external system (the backend API) after mount/param change, not a value derivable from props/state.
    setBrandName(config.brand_name ?? "");
    setPrimaryColor(config.primary_color);
    setSecondaryColor(config.secondary_color);
    setAccentColor(config.accent_color);
    setCompanyEmail(config.company_email ?? "");
    setSupportEmail(config.support_email ?? "");
    setCustomCss(config.custom_css ?? "");
    setCustomJs(config.custom_js ?? "");
    setHideBranding(config.hide_platform_branding);
    setIsActive(config.is_active);
  }, [config]);

  const handleSave = async () => {
    setSaving(true);
    setError(null);
    setSaved(false);
    try {
      await onSave({
        brand_name: brandName || null, primary_color: primaryColor, secondary_color: secondaryColor, accent_color: accentColor,
        company_email: companyEmail || null, support_email: supportEmail || null,
        custom_css: customCss || null, custom_js: customJs || null,
        hide_platform_branding: hideBranding, is_active: isActive,
      });
      setSaved(true);
      setTimeout(() => setSaved(false), 2000);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Could not save your white-label configuration");
    } finally {
      setSaving(false);
    }
  };

  return (
    <div className="flex flex-col gap-4">
      <div className="rounded-xl border border-border bg-surface p-5">
        <div className="flex items-center justify-between">
          <h2 className="text-xs font-medium uppercase text-foreground-muted">White-label</h2>
          <label className="flex items-center gap-2 text-sm text-foreground">
            <input type="checkbox" checked={isActive} onChange={(e) => setIsActive(e.target.checked)} />
            Active
          </label>
        </div>
        <p className="mt-1 text-xs text-foreground-muted">When off, every visitor sees this platform&apos;s own real defaults, regardless of what&apos;s saved below.</p>
      </div>

      <div className="rounded-xl border border-border bg-surface p-5">
        <h2 className="text-xs font-medium uppercase text-foreground-muted">Brand</h2>
        <div className="mt-3 grid grid-cols-1 gap-4 sm:grid-cols-2">
          <div>
            <label htmlFor="wl-brand-name" className="block text-xs font-medium uppercase text-foreground-muted">Company name</label>
            <input
              id="wl-brand-name" type="text" value={brandName} onChange={(e) => setBrandName(e.target.value)}
              className="mt-1 w-full rounded-lg border border-border bg-surface px-3 py-2 text-sm text-foreground"
            />
          </div>
          <label className="mt-6 flex items-center gap-2 text-sm text-foreground">
            <input type="checkbox" checked={hideBranding} onChange={(e) => setHideBranding(e.target.checked)} />
            Hide &quot;RAG SaaS&quot; branding
          </label>
        </div>
        <div className="mt-4 grid grid-cols-1 gap-4 sm:grid-cols-3">
          <ColorPicker label="Primary color" value={primaryColor} onChange={setPrimaryColor} />
          <ColorPicker label="Secondary color" value={secondaryColor} onChange={setSecondaryColor} />
          <ColorPicker label="Accent color" value={accentColor} onChange={setAccentColor} />
        </div>
      </div>

      <div className="rounded-xl border border-border bg-surface p-5">
        <h2 className="text-xs font-medium uppercase text-foreground-muted">Contact</h2>
        <div className="mt-3 grid grid-cols-1 gap-4 sm:grid-cols-2">
          <div>
            <label htmlFor="wl-company-email" className="block text-xs font-medium uppercase text-foreground-muted">Company email</label>
            <input id="wl-company-email" type="email" value={companyEmail} onChange={(e) => setCompanyEmail(e.target.value)} className="mt-1 w-full rounded-lg border border-border bg-surface px-3 py-2 text-sm text-foreground" />
          </div>
          <div>
            <label htmlFor="wl-support-email" className="block text-xs font-medium uppercase text-foreground-muted">Support email</label>
            <input id="wl-support-email" type="email" value={supportEmail} onChange={(e) => setSupportEmail(e.target.value)} className="mt-1 w-full rounded-lg border border-border bg-surface px-3 py-2 text-sm text-foreground" />
          </div>
        </div>
      </div>

      <div className="rounded-xl border border-border bg-surface p-5">
        <CustomCSSEditor value={customCss} onChange={setCustomCss} />
        <div className="mt-4">
          <CustomJSEditor value={customJs} onChange={setCustomJs} />
        </div>
      </div>

      {error && <p className="rounded-lg bg-danger-soft px-3 py-2 text-sm text-danger">{error}</p>}

      <button
        type="button" disabled={saving} onClick={() => void handleSave()}
        className="self-start rounded-lg bg-accent px-5 py-2 text-sm font-medium text-white hover:bg-accent-hover disabled:opacity-50"
      >
        {saved ? "Saved" : saving ? "Saving…" : "Save changes"}
      </button>
    </div>
  );
}
