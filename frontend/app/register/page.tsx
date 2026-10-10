"use client";

import { useRouter } from "next/navigation";
import { useState } from "react";
import AuthShell, { AuthButton, AuthField, AuthLink } from "@/components/auth/AuthShell";
import { ApiError, useAuth } from "@/lib/auth";
import { useTranslation } from "@/lib/i18n";
import OAuthButtons from "@/components/auth/OAuthButtons";

export default function RegisterPage() {
  const router = useRouter();
  const { register } = useAuth();
  const { t } = useTranslation();
  const [fullName, setFullName] = useState("");
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [error, setError] = useState<string | null>(null);
  const [loading, setLoading] = useState(false);

  async function handleSubmit(event: React.FormEvent) {
    event.preventDefault();
    setError(null);
    setLoading(true);
    try {
      await register(email, password, fullName);
      router.push("/dashboard");
    } catch (err) {
      setError(err instanceof ApiError ? String(err.detail) : t("auth.register.error_generic"));
    } finally {
      setLoading(false);
    }
  }

  return (
    <AuthShell
      title={t("auth.register.title")}
      subtitle={t("auth.register.subtitle")}
      error={error}
      footer={
        <p>
          {t("auth.register.have_account")} <AuthLink href="/login" strong>{t("auth.register.login_link")}</AuthLink>
        </p>
      }
    >
      <form onSubmit={handleSubmit}>
        <AuthField label={t("auth.register.full_name")} type="text" value={fullName} onChange={(e) => setFullName(e.target.value)} autoComplete="name" />
        <AuthField label={t("auth.login.email")} type="email" required value={email} onChange={(e) => setEmail(e.target.value)} autoComplete="email" />
        <AuthField label={t("auth.login.password")} type="password" required minLength={8} value={password} onChange={(e) => setPassword(e.target.value)} autoComplete="new-password" />
        <AuthButton disabled={loading}>{loading ? t("auth.register.submitting") : t("auth.register.submit")}</AuthButton>
      </form>
      <OAuthButtons />
    </AuthShell>
  );
}
