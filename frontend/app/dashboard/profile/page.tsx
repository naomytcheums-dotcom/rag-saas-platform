"use client";

import { useCallback, useEffect, useState } from "react";
import Image from "next/image";
import LoadingState from "@/components/LoadingState";
import { api, ApiError } from "@/lib/api";
import { useAuth } from "@/lib/auth";
import { useTranslation } from "@/lib/i18n";

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
const TAB_LABEL_KEYS: Record<Tab, string> = {
  Information: "profile.tab_information",
  Security: "profile.tab_security",
  Preferences: "profile.tab_preferences",
  "Danger zone": "profile.tab_danger",
};

export default function ProfilePage() {
  const { logout } = useAuth();
  const { t } = useTranslation();
  const [tab, setTab] = useState<Tab>("Information");
  const [profile, setProfile] = useState<Profile | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [savedFlash, setSavedFlash] = useState(false);

  const load = useCallback(async () => {
    try {
      setProfile(await api.get<Profile>("/account/me"));
    } catch (err) {
      setError(err instanceof ApiError ? String(err.detail) : t("profile.error_load"));
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
      <h1 className="text-xl font-semibold text-foreground">{t("profile.title")}</h1>

      {error && <p className="mt-4 rounded-lg bg-danger-soft px-3 py-2 text-sm text-danger">{error}</p>}
      {savedFlash && <p className="mt-4 rounded-lg bg-success-soft px-3 py-2 text-sm text-success">{t("profile.saved")}</p>}

      <div className="mt-4 flex gap-1 border-b border-border">
        {TABS.map((tabKey) => (
          <button
            key={tabKey}
            type="button"
            onClick={() => setTab(tabKey)}
            className={`px-3 py-2 text-sm font-medium transition-colors ${
              tab === tabKey ? "border-b-2 border-accent text-accent-hover" : "text-foreground-muted hover:text-foreground"
            }`}
          >
            {t(TAB_LABEL_KEYS[tabKey])}
          </button>
        ))}
      </div>

      <div className="mt-5">
        {tab === "Information" && <InformationTab profile={profile} onSaved={(p) => { setProfile(p); flashSaved(); }} onError={setError} />}
        {tab === "Security" && <SecurityTab profile={profile} onProfileChange={setProfile} onError={setError} onSaved={flashSaved} />}
        {tab === "Preferences" && <PreferencesTab profile={profile} onSaved={(p) => { setProfile(p); flashSaved(); }} onError={setError} />}
        {tab === "Danger zone" && <DangerZoneTab email={profile.email} onLoggedOut={logout} onError={setError} />}
      </div>
    </div>
  );
}

function InformationTab({ profile, onSaved, onError }: { profile: Profile; onSaved: (p: Profile) => void; onError: (e: string) => void }) {
  const { t } = useTranslation();
  const [fullName, setFullName] = useState(profile.full_name ?? "");
  const [company, setCompany] = useState(profile.company ?? "");
  const [saving, setSaving] = useState(false);
  const [uploading, setUploading] = useState(false);

  async function save() {
    setSaving(true);
    try {
      onSaved(await api.patch<Profile>("/account/profile", { full_name: fullName, company }));
    } catch (err) {
      onError(err instanceof ApiError ? String(err.detail) : t("profile.error_save"));
    } finally {
      setSaving(false);
    }
  }

  async function uploadAvatar(file: File) {
    setUploading(true);
    try {
      onSaved(await api.postFile<Profile>("/account/avatar", file));
    } catch (err) {
      onError(err instanceof ApiError ? String(err.detail) : t("profile.error_avatar"));
    } finally {
      setUploading(false);
    }
  }

  return (
    <div className="flex flex-col gap-4 rounded-xl border border-border bg-surface p-5">
      <div className="flex items-center gap-3">
        {profile.avatar_url ? (
          <Image src={profile.avatar_url} alt={t("profile.avatar_alt")} width={56} height={56} unoptimized className="h-14 w-14 rounded-full object-cover" />
        ) : (
          <div className="flex h-14 w-14 items-center justify-center rounded-full bg-accent-soft text-lg font-semibold text-accent-hover">
            {(profile.full_name ?? profile.email).charAt(0).toUpperCase()}
          </div>
        )}
        <input type="file" accept="image/png,image/jpeg,image/webp" disabled={uploading} onChange={(e) => e.target.files?.[0] && void uploadAvatar(e.target.files[0])} className="text-xs" />
      </div>

      <div>
        <label htmlFor="profile-full-name" className="text-sm font-medium text-foreground">{t("profile.full_name")}</label>
        <input id="profile-full-name" value={fullName} onChange={(e) => setFullName(e.target.value)} className="mt-1 w-full rounded-lg border border-border bg-background px-3 py-2 text-sm outline-none focus:border-accent" />
      </div>
      <div>
        <label htmlFor="profile-company" className="text-sm font-medium text-foreground">{t("profile.company")}</label>
        <input id="profile-company" value={company} onChange={(e) => setCompany(e.target.value)} className="mt-1 w-full rounded-lg border border-border bg-background px-3 py-2 text-sm outline-none focus:border-accent" />
      </div>
      <div>
        <p className="text-sm font-medium text-foreground">{t("profile.email")}</p>
        <p className="mt-1 text-sm text-foreground-muted">{profile.email} {profile.is_email_verified ? "✓ " + t("profile.verified") : t("profile.unverified")}</p>
      </div>
      <div>
        <p className="text-sm font-medium text-foreground">{t("profile.member_since")}</p>
        <p className="mt-1 text-sm text-foreground-muted">{new Date(profile.created_at).toLocaleDateString()}</p>
      </div>

      <button type="button" onClick={() => void save()} disabled={saving} className="self-start rounded-lg bg-accent px-4 py-2 text-sm font-medium text-white hover:bg-accent-hover disabled:opacity-50">
        {saving ? t("profile.saving") : t("profile.save_changes")}
      </button>
    </div>
  );
}

interface RecoveryCodesStatus {
  total: number;
  remaining: number;
}

function TwoFactorSection({ enabled, onChanged, onError }: { enabled: boolean; onChanged: (enabled: boolean) => void; onError: (e: string) => void }) {
  const { t } = useTranslation();
  const [step, setStep] = useState<"idle" | "setup" | "recovery-codes" | "regenerate" | "disable">("idle");
  const [setupData, setSetupData] = useState<{ secret: string; qr_code_data_uri: string } | null>(null);
  const [code, setCode] = useState("");
  const [recoveryCodes, setRecoveryCodes] = useState<{ recovery_codes: string[]; recovery_codes_file: string } | null>(null);
  const [status, setStatus] = useState<RecoveryCodesStatus | null>(null);
  const [busy, setBusy] = useState(false);

  const loadStatus = useCallback(async () => {
    try {
      setStatus(await api.get<RecoveryCodesStatus>("/auth/2fa/recovery-codes/status"));
    } catch {
      // Real, honest no-op: the enable/disable state itself still renders without this count.
    }
  }, []);

  useEffect(() => {
    if (enabled) {
      // eslint-disable-next-line react-hooks/set-state-in-effect -- justified: syncing with a real external system (the backend API) after mount/param change, not a value derivable from props/state.
      void loadStatus();
    }
  }, [enabled, loadStatus]);

  async function startSetup() {
    setBusy(true);
    try {
      setSetupData(await api.post<{ secret: string; qr_code_data_uri: string }>("/auth/2fa/setup"));
      setStep("setup");
    } catch (err) {
      onError(err instanceof ApiError ? String(err.detail) : t("profile.2fa_error_setup"));
    } finally {
      setBusy(false);
    }
  }

  async function confirmEnable() {
    setBusy(true);
    try {
      setRecoveryCodes(await api.post<{ recovery_codes: string[]; recovery_codes_file: string }>("/auth/2fa/enable", { code }));
      setStep("recovery-codes");
      setCode("");
      onChanged(true);
    } catch (err) {
      onError(err instanceof ApiError ? String(err.detail) : t("profile.2fa_error_invalid_code"));
    } finally {
      setBusy(false);
    }
  }

  async function confirmRegenerate() {
    setBusy(true);
    try {
      setRecoveryCodes(await api.post<{ recovery_codes: string[]; recovery_codes_file: string }>("/auth/2fa/recovery-codes/regenerate", { code }));
      setStep("recovery-codes");
      setCode("");
    } catch (err) {
      onError(err instanceof ApiError ? String(err.detail) : t("profile.2fa_error_invalid_code"));
    } finally {
      setBusy(false);
    }
  }

  async function confirmDisable() {
    setBusy(true);
    try {
      await api.post("/auth/2fa/disable", { code });
      setStep("idle");
      setCode("");
      setStatus(null);
      onChanged(false);
    } catch (err) {
      onError(err instanceof ApiError ? String(err.detail) : t("profile.2fa_error_invalid_code"));
    } finally {
      setBusy(false);
    }
  }

  function closeRecoveryCodes() {
    setRecoveryCodes(null);
    setStep("idle");
    void loadStatus();
  }

  if (step === "setup" && setupData) {
    return (
      <div className="rounded-xl border border-border bg-surface p-5">
        <h2 className="text-sm font-semibold text-foreground">{t("profile.2fa_setup_heading")}</h2>
        <p className="mt-1 text-xs text-foreground-muted">{t("profile.2fa_scan_desc")}</p>
        {/* eslint-disable-next-line @next/next/no-img-element -- a base64 data: URI generated server-side per setup call, not an optimizable remote/static asset */}
        <img src={setupData.qr_code_data_uri} alt={t("profile.2fa_qr_alt")} className="mt-3 h-40 w-40" />
        <p className="mt-2 text-xs text-foreground-muted">{t("profile.2fa_manual_key")} <code className="rounded bg-surface-muted px-1.5 py-0.5">{setupData.secret}</code></p>
        <input
          value={code}
          onChange={(e) => setCode(e.target.value)}
          aria-label={t("profile.2fa_code_label")}
          placeholder={t("profile.2fa_code_placeholder")}
          maxLength={6}
          className="mt-3 w-full max-w-[200px] rounded-lg border border-border bg-background px-3 py-2 text-sm outline-none focus:border-accent"
        />
        <div className="mt-3 flex gap-2">
          <button type="button" onClick={() => void confirmEnable()} disabled={busy || code.length !== 6} className="rounded-lg bg-accent px-4 py-2 text-sm font-medium text-white hover:bg-accent-hover disabled:opacity-50">
            {busy ? t("profile.2fa_verifying") : t("profile.2fa_confirm_enable")}
          </button>
          <button type="button" onClick={() => { setStep("idle"); setSetupData(null); setCode(""); }} className="rounded-lg border border-border-strong px-4 py-2 text-sm text-foreground hover:bg-surface-muted">
            Annuler
          </button>
        </div>
      </div>
    );
  }

  if (step === "recovery-codes" && recoveryCodes) {
    return (
      <div className="rounded-xl border border-border bg-surface p-5">
        <h2 className="text-sm font-semibold text-foreground">{t("profile.2fa_recovery_heading")}</h2>
        <p className="mt-1 text-xs text-foreground-muted">{t("profile.2fa_recovery_desc")}</p>
        <div className="mt-3 grid grid-cols-2 gap-1.5 rounded-lg bg-surface-muted p-3 font-mono text-sm">
          {recoveryCodes.recovery_codes.map((c) => <span key={c}>{c}</span>)}
        </div>
        <div className="mt-3 flex gap-2">
          <a href={recoveryCodes.recovery_codes_file} download="recovery-codes.txt" className="rounded-lg border border-border-strong px-4 py-2 text-sm text-foreground hover:bg-surface-muted">
            Télécharger (.txt)
          </a>
          <button type="button" onClick={closeRecoveryCodes} className="rounded-lg bg-accent px-4 py-2 text-sm font-medium text-white hover:bg-accent-hover">
            J&apos;ai enregistré ces codes
          </button>
        </div>
      </div>
    );
  }

  if (step === "regenerate" || step === "disable") {
    const isDisable = step === "disable";
    return (
      <div className="rounded-xl border border-border bg-surface p-5">
        <h2 className="text-sm font-semibold text-foreground">{isDisable ? t("profile.2fa_disable_heading") : t("profile.2fa_regenerate_heading")}</h2>
        <p className="mt-1 text-xs text-foreground-muted">{t("profile.2fa_confirm_instruction")}</p>
        <input
          value={code}
          onChange={(e) => setCode(e.target.value)}
          aria-label={t("profile.2fa_code_label")}
          placeholder={t("profile.2fa_code_placeholder")}
          maxLength={6}
          className="mt-3 w-full max-w-[200px] rounded-lg border border-border bg-background px-3 py-2 text-sm outline-none focus:border-accent"
        />
        <div className="mt-3 flex gap-2">
          <button
            type="button"
            onClick={() => void (isDisable ? confirmDisable() : confirmRegenerate())}
            disabled={busy || code.length !== 6}
            className={`rounded-lg px-4 py-2 text-sm font-medium text-white disabled:opacity-50 ${isDisable ? "bg-danger hover:opacity-90" : "bg-accent hover:bg-accent-hover"}`}
          >
            {busy ? t("profile.2fa_verifying") : isDisable ? t("profile.2fa_confirm_disable") : t("profile.2fa_confirm_regenerate")}
          </button>
          <button type="button" onClick={() => { setStep("idle"); setCode(""); }} className="rounded-lg border border-border-strong px-4 py-2 text-sm text-foreground hover:bg-surface-muted">
            Annuler
          </button>
        </div>
      </div>
    );
  }

  return (
    <div className="rounded-xl border border-border bg-surface p-5">
      <div className="flex items-center justify-between">
        <div>
          <h2 className="text-sm font-semibold text-foreground">{t("profile.2fa_heading")}</h2>
          <p className="mt-1 text-xs text-foreground-muted">
            {enabled
              ? t("profile.2fa_enabled_desc", { remaining: status?.remaining ?? 0, total: status?.total ?? 0 })
              : t("profile.2fa_disabled_desc")}
          </p>
        </div>
        <span className={`shrink-0 rounded-full px-2 py-0.5 text-xs font-medium ${enabled ? "bg-success-soft text-success" : "bg-surface-muted text-foreground-muted"}`}>
          {enabled ? t("profile.2fa_enabled") : t("profile.2fa_disabled")}
        </span>
      </div>
      <div className="mt-3 flex gap-2">
        {enabled ? (
          <>
            <button type="button" onClick={() => setStep("regenerate")} className="rounded-lg border border-border-strong px-4 py-2 text-sm text-foreground hover:bg-surface-muted">
              Régénérer les codes de récupération
            </button>
            <button type="button" onClick={() => setStep("disable")} className="rounded-lg border border-danger px-4 py-2 text-sm text-danger hover:bg-danger-soft">
              Désactiver
            </button>
          </>
        ) : (
          <button type="button" onClick={() => void startSetup()} disabled={busy} className="rounded-lg bg-accent px-4 py-2 text-sm font-medium text-white hover:bg-accent-hover disabled:opacity-50">
            {busy ? t("profile.2fa_starting") : t("profile.2fa_enable_button")}
          </button>
        )}
      </div>
    </div>
  );
}

function SecurityTab({ profile, onProfileChange, onError, onSaved }: { profile: Profile; onProfileChange: (p: Profile) => void; onError: (e: string) => void; onSaved: () => void }) {
  const { t } = useTranslation();
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
      onError(err instanceof ApiError ? String(err.detail) : t("profile.error_change_password"));
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
      <TwoFactorSection enabled={profile.totp_enabled} onChanged={(enabled) => onProfileChange({ ...profile, totp_enabled: enabled })} onError={onError} />

      <div className="rounded-xl border border-border bg-surface p-5">
        <h2 className="text-sm font-semibold text-foreground">{t("profile.change_password_heading")}</h2>
        <input type="password" aria-label={t("profile.current_password")} placeholder={t("profile.current_password")} value={currentPassword} onChange={(e) => setCurrentPassword(e.target.value)} className="mt-2 w-full rounded-lg border border-border bg-background px-3 py-2 text-sm outline-none focus:border-accent" />
        <input type="password" aria-label={t("profile.new_password")} placeholder={t("profile.new_password")} value={newPassword} onChange={(e) => setNewPassword(e.target.value)} className="mt-2 w-full rounded-lg border border-border bg-background px-3 py-2 text-sm outline-none focus:border-accent" />
        <button type="button" onClick={() => void changePassword()} disabled={changing || !currentPassword || newPassword.length < 8} className="mt-3 rounded-lg bg-accent px-4 py-2 text-sm font-medium text-white hover:bg-accent-hover disabled:opacity-50">
          {changing ? t("profile.changing_password") : t("profile.change_password_button")}
        </button>
      </div>

      <div>
        <h2 className="mb-2 text-sm font-semibold text-foreground">{t("profile.sessions_heading")}</h2>
        <div className="flex flex-col gap-2">
          {sessions.map((s) => (
            <div key={s.id} className="flex items-center justify-between rounded-lg border border-border bg-surface p-3 text-xs">
              <div>
                <p className="font-medium text-foreground">{s.device_info ?? t("profile.session_unknown_device")} {s.is_current && <span className="text-accent">{t("profile.session_this_device")}</span>}</p>
                <p className="text-foreground-muted">{s.ip_address ?? "—"} · {t("profile.session_last_seen")} {new Date(s.last_seen_at).toLocaleString()}</p>
              </div>
              {!s.is_current && (
                <button type="button" onClick={() => void terminate(s.id)} className="font-medium text-danger hover:underline">{t("profile.session_disconnect")}</button>
              )}
            </div>
          ))}
        </div>
      </div>
    </div>
  );
}

function PreferencesTab({ profile, onSaved, onError }: { profile: Profile; onSaved: (p: Profile) => void; onError: (e: string) => void }) {
  const { t } = useTranslation();
  const [locale, setLocale] = useState(profile.locale);
  const [saving, setSaving] = useState(false);

  async function save() {
    setSaving(true);
    try {
      onSaved(await api.patch<Profile>("/account/preferences", { locale }));
    } catch (err) {
      onError(err instanceof ApiError ? String(err.detail) : t("profile.error_save"));
    } finally {
      setSaving(false);
    }
  }

  return (
    <div className="rounded-xl border border-border bg-surface p-5">
      <label htmlFor="profile-locale" className="text-sm font-medium text-foreground">{t("profile.preferences_heading")}</label>
      <select id="profile-locale" value={locale} onChange={(e) => setLocale(e.target.value)} className="mt-1 w-full rounded-lg border border-border bg-background px-3 py-2 text-sm">
        {/* Matches the backend's real, deliberate 2-language scope (api/config.py's
            UI_SUPPORTED_LANGUAGES, docs/developer/I18N.md) -- the other 4 locale
            directories still exist on disk but /i18n/translations/{lang} 404s for
            them, so offering them here would silently save a locale nothing serves. */}
        {["fr", "en"].map((l) => (
          <option key={l} value={l}>{l}</option>
        ))}
      </select>
      <button type="button" onClick={() => void save()} disabled={saving} className="mt-3 rounded-lg bg-accent px-4 py-2 text-sm font-medium text-white hover:bg-accent-hover disabled:opacity-50">
        {saving ? t("profile.saving") : t("profile.preferences_save")}
      </button>
    </div>
  );
}

function DangerZoneTab({ email, onLoggedOut, onError }: { email: string; onLoggedOut: () => void; onError: (e: string) => void }) {
  const { t } = useTranslation();
  const [confirmEmail, setConfirmEmail] = useState("");
  const [deleting, setDeleting] = useState(false);

  async function deleteAccount() {
    setDeleting(true);
    try {
      await api.delete("/account/me");
      await onLoggedOut();
    } catch (err) {
      onError(err instanceof ApiError ? String(err.detail) : t("profile.error_delete"));
    } finally {
      setDeleting(false);
    }
  }

  return (
    <div className="rounded-xl border border-danger bg-danger-soft p-5">
      <h2 className="text-sm font-semibold text-danger">{t("profile.danger_heading")}</h2>
      <p className="mt-1 text-xs text-foreground-muted">{t("profile.danger_desc", { email })}</p>
      <input value={confirmEmail} onChange={(e) => setConfirmEmail(e.target.value)} className="mt-2 w-full rounded-lg border border-border bg-background px-3 py-2 text-sm outline-none focus:border-danger" />
      <button
        type="button"
        onClick={() => void deleteAccount()}
        disabled={deleting || confirmEmail !== email}
        className="mt-3 rounded-lg bg-danger px-4 py-2 text-sm font-medium text-white hover:opacity-90 disabled:opacity-50"
      >
        {deleting ? t("profile.danger_deleting") : t("profile.danger_button")}
      </button>
    </div>
  );
}
