"use client";

import { useCallback, useEffect, useState } from "react";
import Image from "next/image";
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
      setError(err instanceof ApiError ? String(err.detail) : "Échec du chargement de la configuration du widget");
    }
  }, [org]);

  useEffect(() => {
    // eslint-disable-next-line react-hooks/set-state-in-effect -- justified: syncing with a real external system (the backend API) after mount/param change, not a value derivable from props/state.
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
      setError(err instanceof ApiError ? String(err.detail) : "Échec de l'enregistrement");
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
      setError(err instanceof ApiError ? String(err.detail) : "Échec de l'envoi du logo");
    }
  }

  const scriptSnippet = publicKey
    ? `<script src="${process.env.NEXT_PUBLIC_API_URL ?? "https://your-instance.example.com"}/widget/script.js" data-key="${publicKey}"></script>`
    : "";

  return (
    <div className="mx-auto max-w-2xl">
      <h1 className="text-xl font-semibold text-foreground">Widget</h1>
      <p className="mt-1 text-sm text-foreground-muted">Personnalisez le widget de conversation embarquable pour votre site web.</p>

      {error && <p className="mt-4 rounded-lg bg-danger-soft px-3 py-2 text-sm text-danger">{error}</p>}
      {savedFlash && <p className="mt-4 rounded-lg bg-success-soft px-3 py-2 text-sm text-success">Enregistré !</p>}

      <div className="mt-6 flex flex-col gap-5 rounded-xl border border-border bg-surface p-5">
        <div>
          <label htmlFor="widget-name" className="text-sm font-medium text-foreground">Nom du widget</label>
          <input id="widget-name" value={name} onChange={(e) => setName(e.target.value)} className="mt-1 w-full rounded-lg border border-border bg-background px-3 py-2 text-sm outline-none focus:border-accent" />
        </div>

        <div>
          <label htmlFor="widget-welcome" className="text-sm font-medium text-foreground">Message de bienvenue</label>
          <textarea id="widget-welcome" value={welcome} onChange={(e) => setWelcome(e.target.value)} rows={2} className="mt-1 w-full resize-none rounded-lg border border-border bg-background px-3 py-2 text-sm outline-none focus:border-accent" />
        </div>

        <div>
          <p className="text-sm font-medium text-foreground">Logo</p>
          <div className="mt-1 flex items-center gap-3">
            {logoUrl && <Image src={logoUrl} alt="Logo du widget" width={40} height={40} unoptimized className="h-10 w-10 rounded-full object-cover" />}
            <input type="file" aria-label="Logo du widget" accept="image/png,image/jpeg,image/webp" onChange={(e) => e.target.files?.[0] && void uploadLogo(e.target.files[0])} className="text-xs" />
          </div>
        </div>

        <div className="grid grid-cols-2 gap-4">
          <div>
            <label htmlFor="widget-primary-color" className="text-sm font-medium text-foreground">Couleur principale</label>
            <input id="widget-primary-color" type="color" value={colors.primary_color} onChange={(e) => setColors((c) => ({ ...c, primary_color: e.target.value }))} className="mt-1 h-9 w-full rounded-lg border border-border" />
          </div>
          <div>
            <label htmlFor="widget-header-color" className="text-sm font-medium text-foreground">Couleur de l&apos;en-tête</label>
            <input id="widget-header-color" type="color" value={colors.header_background} onChange={(e) => setColors((c) => ({ ...c, header_background: e.target.value }))} className="mt-1 h-9 w-full rounded-lg border border-border" />
          </div>
        </div>

        <div>
          <p className="text-sm font-medium text-foreground" id="widget-position-label">Position</p>
          <div className="mt-1 flex flex-wrap gap-1.5" role="group" aria-labelledby="widget-position-label">
            {POSITIONS.map((p) => (
              <button key={p} type="button" aria-pressed={position === p} onClick={() => setPosition(p)} className={`rounded-full border px-2.5 py-1 text-xs ${position === p ? "border-accent bg-accent text-white" : "border-border-strong text-foreground-muted"}`}>
                {p}
              </button>
            ))}
          </div>
        </div>

        <div>
          <p className="text-sm font-medium text-foreground" id="widget-theme-label">Thème</p>
          <div className="mt-1 flex flex-wrap gap-1.5" role="group" aria-labelledby="widget-theme-label">
            {THEMES.map((t) => (
              <button key={t} type="button" aria-pressed={theme === t} onClick={() => setTheme(t)} className={`rounded-full border px-2.5 py-1 text-xs ${theme === t ? "border-accent bg-accent text-white" : "border-border-strong text-foreground-muted"}`}>
                {t}
              </button>
            ))}
          </div>
        </div>

        <button type="button" onClick={() => void save()} disabled={saving} className="self-start rounded-lg bg-accent px-4 py-2 text-sm font-medium text-white hover:bg-accent-hover disabled:opacity-50">
          {saving ? "Enregistrement…" : "Enregistrer les modifications"}
        </button>
      </div>

      {scriptSnippet && (
        <div className="mt-6 rounded-xl border border-border bg-surface p-4">
          <h2 className="text-sm font-semibold text-foreground">Intégrer sur votre site</h2>
          <code className="mt-2 block overflow-x-auto rounded-lg bg-background p-3 text-xs">{scriptSnippet}</code>
        </div>
      )}

      {publicKey && (
        <div className="mt-6 rounded-xl border border-border bg-surface p-4">
          <h2 className="text-sm font-semibold text-foreground">Aperçu en direct</h2>
          <p className="mt-1 text-xs text-foreground-muted">Ceci est le vrai iframe du widget en direct — enregistrez vos modifications ci-dessus pour les voir reflétées ici.</p>
          <div className="mt-3 overflow-hidden rounded-xl border border-border" style={{ height: 480 }}>
            <iframe
              key={`${theme}-${colors.primary_color}-${colors.header_background}-${position}`}
              src={`${process.env.NEXT_PUBLIC_API_URL ?? "http://localhost:8000"}/widget/iframe?key=${publicKey}`}
              className="h-full w-full"
              title="Aperçu du widget"
            />
          </div>
        </div>
      )}
    </div>
  );
}
