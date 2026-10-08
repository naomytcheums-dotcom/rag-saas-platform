"use client";

import { useState } from "react";
import AuthShell, { AuthButton, AuthField, AuthLink } from "@/components/auth/AuthShell";
import { api, ApiError } from "@/lib/api";
import { useTranslation } from "@/lib/i18n";

export default function ForgotPasswordPage() {
  const { t } = useTranslation();
  const [email, setEmail] = useState("");
  const [sent, setSent] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [loading, setLoading] = useState(false);

  async function handleSubmit(event: React.FormEvent) {
    event.preventDefault();
    setError(null);
    setLoading(true);
    try {
      await api.post("/auth/password/forgot", { email });
      setSent(true);
    } catch (err) {
      setError(err instanceof ApiError ? String(err.detail) : t("auth.forgot.error_generic"));
    } finally {
      setLoading(false);
    }
  }

  return (
    <AuthShell
      title={t("auth.forgot.title")}
      subtitle={t("auth.forgot.subtitle")}
      error={error}
      footer={<AuthLink href="/login" strong>{t("auth.forgot.back_to_login")}</AuthLink>}
    >
      {sent ? (
        <p className="mt-6 rounded-lg bg-success-soft px-3 py-2 text-sm text-success">{t("auth.forgot.sent")}</p>
      ) : (
        <form onSubmit={handleSubmit}>
          <AuthField label={t("auth.login.email")} type="email" required value={email} onChange={(e) => setEmail(e.target.value)} autoComplete="email" />
          <AuthButton disabled={loading}>{loading ? t("auth.forgot.submitting") : t("auth.forgot.submit")}</AuthButton>
        </form>
      )}
    </AuthShell>
  );
}
