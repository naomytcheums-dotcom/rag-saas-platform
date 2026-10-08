"use client";

import { useRouter } from "next/navigation";
import { useState } from "react";
import AuthShell, { AuthButton, AuthField, AuthLink } from "@/components/auth/AuthShell";
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
    <AuthShell
      title={t("auth.login.title")}
      subtitle={t("auth.login.subtitle")}
      error={error}
      footer={
        <p>
          {t("auth.login.no_account")} <AuthLink href="/register" strong>{t("auth.login.signup_link")}</AuthLink>
        </p>
      }
    >
      {mfaToken ? (
        <form onSubmit={handleMfaSubmit}>
          <AuthField label={t("auth.mfa.label")} type="text" inputMode="numeric" autoFocus value={code} onChange={(e) => setCode(e.target.value)} />
          <AuthButton disabled={loading}>{loading ? t("auth.mfa.submitting") : t("auth.mfa.submit")}</AuthButton>
        </form>
      ) : (
        <form onSubmit={handleSubmit}>
          <AuthField label={t("auth.login.email")} type="email" required value={email} onChange={(e) => setEmail(e.target.value)} autoComplete="email" />
          <AuthField label={t("auth.login.password")} type="password" required value={password} onChange={(e) => setPassword(e.target.value)} autoComplete="current-password" />
          <div className="-mt-[15px] mb-[15px] flex items-center justify-between text-[14.5px]">
            <label htmlFor="remember-me" className="flex items-center gap-1">
              <input id="remember-me" type="checkbox" checked={rememberMe} onChange={(e) => setRememberMe(e.target.checked)} className="mr-[3px] accent-white" />
              {t("auth.login.remember_me")}
            </label>
            <AuthLink href="/forgot-password">{t("auth.login.forgot_password")}</AuthLink>
          </div>
          <AuthButton disabled={loading}>{loading ? t("auth.login.submitting") : t("auth.login.submit")}</AuthButton>
        </form>
      )}
    </AuthShell>
  );
}
