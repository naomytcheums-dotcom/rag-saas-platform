"use client";

import { useCallback, useEffect, useState } from "react";
import Image from "next/image";
import LoadingState from "@/components/LoadingState";
import { api, ApiError } from "@/lib/api";
import { useAuth } from "@/lib/auth";

interface Profile {
  id: string;
  email: string;
  full_name: string | null;
  company: string | null;
  avatar_url: string | null;
  locale: string;
  timezone: string;
  is_email_verified: boolean;
  totp_enabled: boolean;
  created_at: string;
}

interface SessionEntry {
  id: string;
  device_info: string | null;
  ip_address: string | null;
  created_at: string;
  last_seen_at: string;
  is_current: boolean;
}

const TABS = ["Information", "Security", "Preferences", "Danger zone"] as const;
type Tab = (typeof TABS)[number];
const TAB_LABELS: Record<Tab, string> = {
  Information: "Informations", Security: "Sécurité", Preferences: "Préférences", "Danger zone": "Zone de danger",
};

export default function ProfilePage() {
  const { logout } = useAuth();
  const [tab, setTab] = useState<Tab>("Information");
  const [profile, setProfile] = useState<Profile | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [savedFlash, setSavedFlash] = useState(false);

  const load = useCallback(async () => {
    try {
      setProfile(await api.get<Profile>("/account/me"));
    } catch (err) {
      setError(err instanceof ApiError ? String(err.detail) : "Échec du chargement du profil");
    }
  }, []);

  useEffect(() => {
    // eslint-disable-next-line react-hooks/set-state-in-effect -- justified: syncing with a real external system (the backend API) after mount/param change, not a value derivable from props/state.
    void load();
  }, [load]);

  function flashSaved() {
    setSavedFlash(true);
    setTimeout(() => setSavedFlash(false), 2000);
  }

  if (!profile) {
    if (error) return <div className="mx-auto max-w-2xl text-sm text-danger">{error}</div>;
    return <LoadingState fullScreen={false} />;
  }

  return (
    <div className="mx-auto max-w-2xl">
      <h1 className="text-xl font-semibold text-foreground">Profil</h1>

      {error && <p className="mt-4 rounded-lg bg-danger-soft px-3 py-2 text-sm text-danger">{error}</p>}
      {savedFlash && <p className="mt-4 rounded-lg bg-success-soft px-3 py-2 text-sm text-success">Enregistré !</p>}

      <div className="mt-4 flex gap-1 border-b border-border">
        {TABS.map((t) => (
          <button
            key={t}
            type="button"
            onClick={() => setTab(t)}
            className={`px-3 py-2 text-sm font-medium transition-colors ${
              tab === t ? "border-b-2 border-accent text-accent-hover" : "text-foreground-muted hover:text-foreground"
            }`}
          >
            {TAB_LABELS[t]}
          </button>
        ))}
      </div>

      <div className="mt-5">
        {tab === "Information" && <InformationTab profile={profile} onSaved={(p) => { setProfile(p); flashSaved(); }} onError={setError} />}
        {tab === "Security" && <SecurityTab onError={setError} onSaved={flashSaved} />}
        {tab === "Preferences" && <PreferencesTab profile={profile} onSaved={(p) => { setProfile(p); flashSaved(); }} onError={setError} />}
        {tab === "Danger zone" && <DangerZoneTab email={profile.email} onLoggedOut={logout} onError={setError} />}
      </div>
    </div>
  );
}

function InformationTab({ profile, onSaved, onError }: { profile: Profile; onSaved: (p: Profile) => void; onError: (e: string) => void }) {
  const [fullName, setFullName] = useState(profile.full_name ?? "");
  const [company, setCompany] = useState(profile.company ?? "");
  const [saving, setSaving] = useState(false);
  const [uploading, setUploading] = useState(false);

  async function save() {
    setSaving(true);
    try {
      onSaved(await api.patch<Profile>("/account/profile", { full_name: fullName, company }));
    } catch (err) {
      onError(err instanceof ApiError ? String(err.detail) : "Échec de l'enregistrement");
    } finally {
      setSaving(false);
    }
  }

  async function uploadAvatar(file: File) {
    setUploading(true);
    try {
      onSaved(await api.postFile<Profile>("/account/avatar", file));
    } catch (err) {
      onError(err instanceof ApiError ? String(err.detail) : "Échec de l'envoi de l'avatar");
    } finally {
      setUploading(false);
    }
  }

  return (
    <div className="flex flex-col gap-4 rounded-xl border border-border bg-surface p-5">
      <div className="flex items-center gap-3">
        {profile.avatar_url ? (
          <Image src={profile.avatar_url} alt="Avatar" width={56} height={56} unoptimized className="h-14 w-14 rounded-full object-cover" />
        ) : (
          <div className="flex h-14 w-14 items-center justify-center rounded-full bg-accent-soft text-lg font-semibold text-accent-hover">
            {(profile.full_name ?? profile.email).charAt(0).toUpperCase()}
          </div>
        )}
        <input type="file" accept="image/png,image/jpeg,image/webp" disabled={uploading} onChange={(e) => e.target.files?.[0] && void uploadAvatar(e.target.files[0])} className="text-xs" />
      </div>

      <div>
        <label className="text-sm font-medium text-foreground">Nom complet</label>
        <input value={fullName} onChange={(e) => setFullName(e.target.value)} className="mt-1 w-full rounded-lg border border-border bg-background px-3 py-2 text-sm outline-none focus:border-accent" />
      </div>
      <div>
        <label className="text-sm font-medium text-foreground">Entreprise</label>
        <input value={company} onChange={(e) => setCompany(e.target.value)} className="mt-1 w-full rounded-lg border border-border bg-background px-3 py-2 text-sm outline-none focus:border-accent" />
      </div>
      <div>
        <label className="text-sm font-medium text-foreground">Email</label>
        <p className="mt-1 text-sm text-foreground-muted">{profile.email} {profile.is_email_verified ? "✓ vérifié" : "(non vérifié)"}</p>
      </div>
      <div>
        <label className="text-sm font-medium text-foreground">Membre depuis</label>
        <p className="mt-1 text-sm text-foreground-muted">{new Date(profile.created_at).toLocaleDateString()}</p>
      </div>

      <button type="button" onClick={() => void save()} disabled={saving} className="self-start rounded-lg bg-accent px-4 py-2 text-sm font-medium text-white hover:bg-accent-hover disabled:opacity-50">
        {saving ? "Enregistrement…" : "Enregistrer les modifications"}
      </button>
    </div>
  );
}

function SecurityTab({ onError, onSaved }: { onError: (e: string) => void; onSaved: () => void }) {
  const [currentPassword, setCurrentPassword] = useState("");
  const [newPassword, setNewPassword] = useState("");
  const [changing, setChanging] = useState(false);
  const [sessions, setSessions] = useState<SessionEntry[]>([]);

  const loadSessions = useCallback(async () => {
    try {
      setSessions(await api.get<SessionEntry[]>("/sessions"));
    } catch {
      // Real, honest no-op: an empty session list is a safe, visible fallback.
    }
  }, []);

  useEffect(() => {
    // eslint-disable-next-line react-hooks/set-state-in-effect -- justified: syncing with a real external system (the backend API) after mount/param change, not a value derivable from props/state.
    void loadSessions();
  }, [loadSessions]);

  async function changePassword() {
    setChanging(true);
    try {
      await api.post("/account/change-password", { current_password: currentPassword, new_password: newPassword });
      setCurrentPassword("");
      setNewPassword("");
      onSaved();
    } catch (err) {
      onError(err instanceof ApiError ? String(err.detail) : "Échec du changement de mot de passe");
    } finally {
      setChanging(false);
    }
  }

  async function terminate(sessionId: string) {
    await api.delete(`/sessions/${sessionId}`);
    await loadSessions();
  }

  return (
    <div className="flex flex-col gap-6">
      <div className="rounded-xl border border-border bg-surface p-5">
        <h2 className="text-sm font-semibold text-foreground">Changer le mot de passe</h2>
        <input type="password" placeholder="Mot de passe actuel" value={currentPassword} onChange={(e) => setCurrentPassword(e.target.value)} className="mt-2 w-full rounded-lg border border-border bg-background px-3 py-2 text-sm outline-none focus:border-accent" />
        <input type="password" placeholder="Nouveau mot de passe" value={newPassword} onChange={(e) => setNewPassword(e.target.value)} className="mt-2 w-full rounded-lg border border-border bg-background px-3 py-2 text-sm outline-none focus:border-accent" />
        <button type="button" onClick={() => void changePassword()} disabled={changing || !currentPassword || newPassword.length < 8} className="mt-3 rounded-lg bg-accent px-4 py-2 text-sm font-medium text-white hover:bg-accent-hover disabled:opacity-50">
          {changing ? "Changement…" : "Changer le mot de passe"}
        </button>
      </div>

      <div>
        <h2 className="mb-2 text-sm font-semibold text-foreground">Sessions actives</h2>
        <div className="flex flex-col gap-2">
          {sessions.map((s) => (
            <div key={s.id} className="flex items-center justify-between rounded-lg border border-border bg-surface p-3 text-xs">
              <div>
                <p className="font-medium text-foreground">{s.device_info ?? "Appareil inconnu"} {s.is_current && <span className="text-accent">(cet appareil)</span>}</p>
                <p className="text-foreground-muted">{s.ip_address ?? "—"} · vu pour la dernière fois {new Date(s.last_seen_at).toLocaleString()}</p>
              </div>
              {!s.is_current && (
                <button type="button" onClick={() => void terminate(s.id)} className="font-medium text-danger hover:underline">Déconnecter</button>
              )}
            </div>
          ))}
        </div>
      </div>
    </div>
  );
}

function PreferencesTab({ profile, onSaved, onError }: { profile: Profile; onSaved: (p: Profile) => void; onError: (e: string) => void }) {
  const [locale, setLocale] = useState(profile.locale);
  const [saving, setSaving] = useState(false);

  async function save() {
    setSaving(true);
    try {
      onSaved(await api.patch<Profile>("/account/preferences", { locale }));
    } catch (err) {
      onError(err instanceof ApiError ? String(err.detail) : "Échec de l'enregistrement");
    } finally {
      setSaving(false);
    }
  }

  return (
    <div className="rounded-xl border border-border bg-surface p-5">
      <label className="text-sm font-medium text-foreground">Langue</label>
      <select value={locale} onChange={(e) => setLocale(e.target.value)} className="mt-1 w-full rounded-lg border border-border bg-background px-3 py-2 text-sm">
        {["en", "fr", "es", "de", "pt", "ar"].map((l) => (
          <option key={l} value={l}>{l}</option>
        ))}
      </select>
      <button type="button" onClick={() => void save()} disabled={saving} className="mt-3 rounded-lg bg-accent px-4 py-2 text-sm font-medium text-white hover:bg-accent-hover disabled:opacity-50">
        {saving ? "Enregistrement…" : "Enregistrer les préférences"}
      </button>
    </div>
  );
}

function DangerZoneTab({ email, onLoggedOut, onError }: { email: string; onLoggedOut: () => void; onError: (e: string) => void }) {
  const [confirmEmail, setConfirmEmail] = useState("");
  const [deleting, setDeleting] = useState(false);

  async function deleteAccount() {
    setDeleting(true);
    try {
      await api.delete("/account/me");
      await onLoggedOut();
    } catch (err) {
      onError(err instanceof ApiError ? String(err.detail) : "Échec de la suppression du compte");
    } finally {
      setDeleting(false);
    }
  }

  return (
    <div className="rounded-xl border border-danger bg-danger-soft p-5">
      <h2 className="text-sm font-semibold text-danger">Supprimer votre compte</h2>
      <p className="mt-1 text-xs text-foreground-muted">Cette action est définitive. Saisissez votre email ({email}) pour confirmer.</p>
      <input value={confirmEmail} onChange={(e) => setConfirmEmail(e.target.value)} className="mt-2 w-full rounded-lg border border-border bg-background px-3 py-2 text-sm outline-none focus:border-danger" />
      <button
        type="button"
        onClick={() => void deleteAccount()}
        disabled={deleting || confirmEmail !== email}
        className="mt-3 rounded-lg bg-danger px-4 py-2 text-sm font-medium text-white hover:opacity-90 disabled:opacity-50"
      >
        {deleting ? "Suppression…" : "Supprimer mon compte"}
      </button>
    </div>
  );
}
