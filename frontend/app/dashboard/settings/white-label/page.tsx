"use client";

import { useEffect, useState } from "react";
import { api } from "@/lib/api";
import { useCurrentOrg } from "@/lib/useCurrentOrg";

interface Branding {
  logo_url: string | null;
  favicon_url: string | null;
  primary_color: string;
  secondary_color: string;
  accent_color: string;
  background_color: string;
  text_color: string;
  font_family: string | null;
  custom_css: string | null;
}

const DEFAULT: Branding = {
  logo_url: null, favicon_url: null,
  primary_color: "#3B82F6", secondary_color: "#1E40AF",
  accent_color: "#F59E0B", background_color: "#FFFFFF", text_color: "#111827",
  font_family: null, custom_css: null,
};

export default function WhiteLabelPage() {
  const { org, loading: orgLoading } = useCurrentOrg();
  const [branding, setBranding] = useState<Branding>(DEFAULT);
  const [loading, setLoading] = useState(true);
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [success, setSuccess] = useState(false);

  useEffect(() => {
    if (!org) return;
    api.get<Branding>(`/organizations/${org.id}/branding`)
      .then(setBranding)
      .catch((err) => setError(err.message))
      .finally(() => setLoading(false));
  }, [org]);

  async function handleSave() {
    if (!org) return;
    setSaving(true);
    setError(null);
    setSuccess(false);
    try {
      await api.patch(`/organizations/${org.id}/branding`, branding);
      setSuccess(true);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Erreur");
    } finally {
      setSaving(false);
    }
  }

  if (orgLoading || loading || !org) return <div className="p-6">Chargement...</div>;

  return (
    <div className="p-6 max-w-3xl">
      <h1 className="text-2xl font-semibold mb-6">Personnalisation de la marque</h1>
      {error && <p className="text-danger mb-4">{error}</p>}
      {success && <p className="text-green-600 mb-4">Enregistré</p>}

      <div className="flex flex-col gap-4">
        <label>Logo URL
          <input type="url" value={branding.logo_url ?? ""} onChange={(e) => setBranding({ ...branding, logo_url: e.target.value || null })} className="mt-1 w-full border rounded px-3 py-2" />
        </label>
        <label>Favicon URL
          <input type="url" value={branding.favicon_url ?? ""} onChange={(e) => setBranding({ ...branding, favicon_url: e.target.value || null })} className="mt-1 w-full border rounded px-3 py-2" />
        </label>
        <div className="grid grid-cols-2 gap-4">
          <label>Couleur primaire
            <input type="color" value={branding.primary_color} onChange={(e) => setBranding({ ...branding, primary_color: e.target.value })} className="mt-1 w-full h-10" />
          </label>
          <label>Couleur secondaire
            <input type="color" value={branding.secondary_color} onChange={(e) => setBranding({ ...branding, secondary_color: e.target.value })} className="mt-1 w-full h-10" />
          </label>
          <label>Couleur accent
            <input type="color" value={branding.accent_color} onChange={(e) => setBranding({ ...branding, accent_color: e.target.value })} className="mt-1 w-full h-10" />
          </label>
          <label>Couleur fond
            <input type="color" value={branding.background_color} onChange={(e) => setBranding({ ...branding, background_color: e.target.value })} className="mt-1 w-full h-10" />
          </label>
          <label>Couleur texte
            <input type="color" value={branding.text_color} onChange={(e) => setBranding({ ...branding, text_color: e.target.value })} className="mt-1 w-full h-10" />
          </label>
        </div>
        <label>Police
          <input type="text" value={branding.font_family ?? ""} onChange={(e) => setBranding({ ...branding, font_family: e.target.value || null })} placeholder="Inter, Roboto, ..." className="mt-1 w-full border rounded px-3 py-2" />
        </label>
        <label>CSS personnalisé
          <textarea value={branding.custom_css ?? ""} onChange={(e) => setBranding({ ...branding, custom_css: e.target.value || null })} rows={6} className="mt-1 w-full border rounded px-3 py-2 font-mono text-sm" />
        </label>
        <button onClick={handleSave} disabled={saving} className="bg-accent text-white px-4 py-2 rounded disabled:opacity-50">
          {saving ? "Enregistrement..." : "Enregistrer"}
        </button>
      </div>
    </div>
  );
}
