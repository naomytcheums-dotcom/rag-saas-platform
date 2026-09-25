"use client";

import Link from "next/link";
import { useRouter } from "next/navigation";
import { useState } from "react";
import { ApiError, useAuth } from "@/lib/auth";
import { api } from "@/lib/api";
import { useTranslation } from "@/lib/i18n";

export default function LoginPage() {
  const router = useRouter();
  const { login } = useAuth();
  const { t } = useTranslation();
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [rememberMe, setRememberMe] = useState(true);
  const [mfaToken, setMfaToken] = useState<string | null>(null);
  const [code, setCode] = useState("");
  const [error, setError] = useState<string | null>(null);
  const [loading, setLoading] = useState(false);

  async function handleSubmit(event: React.FormEvent) {
    event.preventDefault();
    setError(null);
    setLoading(true);
    try {
      const result = await login(email, password, rememberMe);
      if (result.mfaRequired && result.mfaToken) {
        setMfaToken(result.mfaToken);
      } else {
        router.push("/dashboard");
      }
    } catch (err) {
      setError(err instanceof ApiError ? String(err.detail) : t("auth.login.error_generic"));
    } finally {
      setLoading(false);
    }
  }

  async function handleMfaSubmit(event: React.FormEvent) {
    event.preventDefault();
    setError(null);
    setLoading(true);
    try {
      const result = await api.post<{ access_token: string }>("/auth/2fa/verify-login", { mfa_token: mfaToken, code });
      window.localStorage.setItem("access_token", result.access_token);
      router.push("/dashboard");
    } catch (err) {
      setError(err instanceof ApiError ? String(err.detail) : t("auth.mfa.error"));
    } finally {
      setLoading(false);
    }
  }

  return (
    <div className="flex min-h-screen items-center justify-center bg-gradient-to-br from-orange-50 to-white px-4">
      <div className="w-full max-w-sm rounded-2xl border border-border bg-surface p-8 shadow-sm">
        <h1 className="mb-1 text-xl font-semibold text-foreground">{t("auth.login.title")}</h1>
        <p className="mb-6 text-sm text-foreground-muted">{t("auth.login.subtitle")}</p>

        {error && <p className="mb-4 rounded-lg bg-danger-soft px-3 py-2 text-sm text-danger">{error}</p>}

        {mfaToken ? (
          <form onSubmit={handleMfaSubmit} className="flex flex-col gap-3">
            <label className="text-sm text-foreground-muted">
              {t("auth.mfa.label")}
              <input
                type="text"
                inputMode="numeric"
                autoFocus
                value={code}
                onChange={(e) => setCode(e.target.value)}
                className="mt-1 w-full rounded-lg border border-border bg-background px-3 py-2 text-sm outline-none focus:border-accent"
                placeholder="123456"
              />
            </label>
            <button type="submit" disabled={loading} className="mt-2 rounded-lg bg-accent px-4 py-2.5 text-sm font-medium text-white hover:bg-accent-hover disabled:opacity-50">
              {loading ? t("auth.mfa.submitting") : t("auth.mfa.submit")}
            </button>
          </form>
        ) : (
          <form onSubmit={handleSubmit} className="flex flex-col gap-3">
            <label className="text-sm text-foreground-muted">
              {t("auth.login.email")}
              <input
                type="email"
                required
                value={email}
                onChange={(e) => setEmail(e.target.value)}
                className="mt-1 w-full rounded-lg border border-border bg-background px-3 py-2 text-sm outline-none focus:border-accent"
                placeholder={t("auth.login.email_placeholder")}
              />
            </label>
            <label className="text-sm text-foreground-muted">
              {t("auth.login.password")}
              <input
                type="password"
                required
                value={password}
                onChange={(e) => setPassword(e.target.value)}
                className="mt-1 w-full rounded-lg border border-border bg-background px-3 py-2 text-sm outline-none focus:border-accent"
                placeholder="••••••••"
              />
            </label>
            <div className="flex items-center justify-between text-sm">
              <label htmlFor="remember-me" className="flex items-center gap-2 text-foreground-muted">
                <input id="remember-me" type="checkbox" checked={rememberMe} onChange={(e) => setRememberMe(e.target.checked)} className="rounded border-border-strong" />
                {t("auth.login.remember_me")}
              </label>
              <Link href="/forgot-password" className="text-accent hover:underline">{t("auth.login.forgot_password")}</Link>
            </div>
            <button type="submit" disabled={loading} className="mt-2 rounded-lg bg-accent px-4 py-2.5 text-sm font-medium text-white hover:bg-accent-hover disabled:opacity-50">
              {loading ? t("auth.login.submitting") : t("auth.login.submit")}
            </button>
          </form>
        )}

        <p className="mt-6 text-center text-sm text-foreground-muted">
          {t("auth.login.no_account")} <Link href="/register" className="font-medium text-accent hover:underline">{t("auth.login.signup_link")}</Link>
        </p>
      </div>
    </div>
  );
}
