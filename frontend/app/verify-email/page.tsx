"use client";

import { useRouter } from "next/navigation";
import { useState } from "react";
import AuthShell, { AuthButton, AuthField, AuthLink } from "@/components/auth/AuthShell";
import { api, ApiError } from "@/lib/api";
import { useTranslation } from "@/lib/i18n";

/** Spec 1.1.4: the signed-in user types the 6-digit code that was e-mailed to them (POST /auth/verify-email/confirm) or asks for a new one (/request). */
export default function VerifyEmailPage() {
  const router = useRouter();
  const { t } = useTranslation();
  const [code, setCode] = useState("");
  const [error, setError] = useState<string | null>(null);
  const [info, setInfo] = useState<string | null>(null);
  const [loading, setLoading] = useState(false);

  async function confirm(event: React.FormEvent) {
    event.preventDefault();
    setError(null);
    setInfo(null);
    setLoading(true);
    try {
      await api.post("/auth/verify-email/confirm", { code: code.trim() });
      router.push("/dashboard/profile");
    } catch (err) {
      setError(err instanceof ApiError ? String(err.detail) : t("auth.verify.error_generic"));
    } finally {
      setLoading(false);
    }
  }

  async function resend() {
    setError(null);
    setInfo(null);
    try {
      await api.post("/auth/verify-email/request", {});
      setInfo(t("auth.verify.sent"));
    } catch (err) {
      setError(err instanceof ApiError ? String(err.detail) : t("auth.verify.error_generic"));
    }
  }

  return (
    <AuthShell
      title={t("auth.verify.title")}
      subtitle={t("auth.verify.subtitle")}
      error={error}
      footer={
        <p>
          <button type="button" onClick={() => void resend()} className="text-white underline">{t("auth.verify.resend")}</button>
          {" · "}
          <AuthLink href="/dashboard">{t("auth.verify.later")}</AuthLink>
        </p>
      }
    >
      {info && <p role="status" className="mt-4 text-center text-sm text-white/85">{info}</p>}
      <form onSubmit={confirm}>
        <AuthField label={t("auth.verify.code")} type="text" inputMode="numeric" autoComplete="one-time-code" maxLength={6} required autoFocus value={code} onChange={(e) => setCode(e.target.value)} />
        <AuthButton disabled={loading || code.trim().length !== 6}>{loading ? t("auth.verify.submitting") : t("auth.verify.submit")}</AuthButton>
      </form>
    </AuthShell>
  );
}
