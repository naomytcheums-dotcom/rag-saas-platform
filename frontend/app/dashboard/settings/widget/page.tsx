"use client";

import { useCallback, useEffect, useState } from "react";
import { api, ApiError } from "@/lib/api";
import { useCurrentOrg } from "@/lib/useCurrentOrg";

const POSITIONS = ["bottom-right", "bottom-left", "top-right", "top-left"];
const THEMES = ["light", "dark", "auto"];

export default function WidgetSettingsPage() {
  const { org } = useCurrentOrg();
  const [publicKey, setPublicKey] = useState<string | null>(null);
  const [name, setName] = useState("");
  const [welcome, setWelcome] = useState("");
  const [position, setPosition] = useState("bottom-right");
  const [theme, setTheme] = useState("auto");
  const [colors, setColors] = useState({ primary_color: "#6C63FF", header_background: "#6C63FF" });
  const [logoUrl, setLogoUrl] = useState<string | null>(null);
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [savedFlash, setSavedFlash] = useState(false);

  const load = useCallback(async () => {
    if (!org) return;
    try {
      const config = await api.get<{
        public_key: string; name: string | null; welcome_message: string | null; position: string; theme: string;
        colors: { primary: string; header_background: string }; logo_url: string | null;
      }>(`/organizations/${org.id}/widget/config`);
      setPublicKey(config.public_key);
      setName(config.name ?? "");
      setWelcome(config.welcome_message ?? "");
      setPosition(config.position);
      setTheme(config.theme);
      setColors({ primary_color: config.colors.primary, header_background: config.colors.header_background });
      setLogoUrl(config.logo_url);
    } catch (err) {
      setError(err instanceof ApiError ? String(err.detail) : "Failed to load widget config");
    }
  }, [org]);

  useEffect(() => {
    void load();
  }, [load]);

  async function save() {
    if (!org) return;
    setSaving(true);
    setError(null);
    try {
      await Promise.all([
        api.patch(`/organizations/${org.id}/widget/config/name`, { name: name || "Assistant" }),
        api.patch(`/organizations/${org.id}/widget/welcome`, { message: welcome }),
        api.patch(`/organizations/${org.id}/widget/position`, { position }),
        api.patch(`/organizations/${org.id}/widget/theme`, { theme }),
        api.patch(`/organizations/${org.id}/widget/config`, colors),
      ]);
      setSavedFlash(true);
      setTimeout(() => setSavedFlash(false), 2000);
      await load();
    } catch (err) {
      setError(err instanceof ApiError ? String(err.detail) : "Failed to save");
    } finally {
      setSaving(false);
    }
  }

  async function uploadLogo(file: File) {
    if (!org) return;
    try {
      const result = await api.postFile<{ logo_url: string }>(`/organizations/${org.id}/widget/logo`, file);
      setLogoUrl(result.logo_url);
    } catch (err) {
      setError(err instanceof ApiError ? String(err.detail) : "Failed to upload logo");
    }
  }

  const scriptSnippet = publicKey
    ? `<script src="${process.env.NEXT_PUBLIC_API_URL ?? "https://your-instance.example.com"}/widget/script.js" data-key="${publicKey}"></script>`
    : "";

  return (
    <div className="mx-auto max-w-2xl">
      <h1 className="text-xl font-semibold text-foreground">Widget</h1>
      <p className="mt-1 text-sm text-foreground-muted">Customize the embeddable chat widget for your website.</p>

      {error && <p className="mt-4 rounded-lg bg-danger-soft px-3 py-2 text-sm text-danger">{error}</p>}
      {savedFlash && <p className="mt-4 rounded-lg bg-success-soft px-3 py-2 text-sm text-success">Saved!</p>}

      <div className="mt-6 flex flex-col gap-5 rounded-xl border border-border bg-surface p-5">
        <div>
          <label className="text-sm font-medium text-foreground">Widget name</label>
          <input value={name} onChange={(e) => setName(e.target.value)} className="mt-1 w-full rounded-lg border border-border bg-background px-3 py-2 text-sm outline-none focus:border-accent" />
        </div>

        <div>
          <label className="text-sm font-medium text-foreground">Welcome message</label>
          <textarea value={welcome} onChange={(e) => setWelcome(e.target.value)} rows={2} className="mt-1 w-full resize-none rounded-lg border border-border bg-background px-3 py-2 text-sm outline-none focus:border-accent" />
        </div>

        <div>
          <label className="text-sm font-medium text-foreground">Logo</label>
          <div className="mt-1 flex items-center gap-3">
            {logoUrl && <img src={logoUrl} alt="Widget logo" className="h-10 w-10 rounded-full object-cover" />}
            <input type="file" accept="image/png,image/jpeg,image/webp" onChange={(e) => e.target.files?.[0] && void uploadLogo(e.target.files[0])} className="text-xs" />
          </div>
        </div>

        <div className="grid grid-cols-2 gap-4">
          <div>
            <label className="text-sm font-medium text-foreground">Primary color</label>
            <input type="color" value={colors.primary_color} onChange={(e) => setColors((c) => ({ ...c, primary_color: e.target.value }))} className="mt-1 h-9 w-full rounded-lg border border-border" />
          </div>
          <div>
            <label className="text-sm font-medium text-foreground">Header color</label>
            <input type="color" value={colors.header_background} onChange={(e) => setColors((c) => ({ ...c, header_background: e.target.value }))} className="mt-1 h-9 w-full rounded-lg border border-border" />
          </div>
        </div>

        <div>
          <label className="text-sm font-medium text-foreground">Position</label>
          <div className="mt-1 flex flex-wrap gap-1.5">
            {POSITIONS.map((p) => (
              <button key={p} type="button" onClick={() => setPosition(p)} className={`rounded-full border px-2.5 py-1 text-xs ${position === p ? "border-accent bg-accent text-white" : "border-border-strong text-foreground-muted"}`}>
                {p}
              </button>
            ))}
          </div>
        </div>

        <div>
          <label className="text-sm font-medium text-foreground">Theme</label>
          <div className="mt-1 flex flex-wrap gap-1.5">
            {THEMES.map((t) => (
              <button key={t} type="button" onClick={() => setTheme(t)} className={`rounded-full border px-2.5 py-1 text-xs ${theme === t ? "border-accent bg-accent text-white" : "border-border-strong text-foreground-muted"}`}>
                {t}
              </button>
            ))}
          </div>
        </div>

        <button type="button" onClick={() => void save()} disabled={saving} className="self-start rounded-lg bg-accent px-4 py-2 text-sm font-medium text-white hover:bg-accent-hover disabled:opacity-50">
          {saving ? "Saving…" : "Save changes"}
        </button>
      </div>

      {scriptSnippet && (
        <div className="mt-6 rounded-xl border border-border bg-surface p-4">
          <h2 className="text-sm font-semibold text-foreground">Embed on your site</h2>
          <code className="mt-2 block overflow-x-auto rounded-lg bg-background p-3 text-xs">{scriptSnippet}</code>
        </div>
      )}

      {publicKey && (
        <div className="mt-6 rounded-xl border border-border bg-surface p-4">
          <h2 className="text-sm font-semibold text-foreground">Live preview</h2>
          <p className="mt-1 text-xs text-foreground-muted">This is the real, live widget iframe — save your changes above to see them reflected here.</p>
          <div className="mt-3 overflow-hidden rounded-xl border border-border" style={{ height: 480 }}>
            <iframe
              key={`${theme}-${colors.primary_color}-${colors.header_background}-${position}`}
              src={`${process.env.NEXT_PUBLIC_API_URL ?? "http://localhost:8000"}/widget/iframe?key=${publicKey}`}
              className="h-full w-full"
              title="Widget preview"
            />
          </div>
        </div>
      )}
    </div>
  );
}
