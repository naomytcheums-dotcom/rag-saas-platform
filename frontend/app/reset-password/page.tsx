"use client";

import { useRouter, useSearchParams } from "next/navigation";
import { Suspense, useState } from "react";
import AuthShell, { AuthButton, AuthField, AuthLink } from "@/components/auth/AuthShell";
import { api, ApiError } from "@/lib/api";

function ResetPasswordForm({ onError }: { onError: (message: string | null) => void }) {
  const router = useRouter();
  const token = useSearchParams().get("token") ?? "";
  const [password, setPassword] = useState("");
  const [confirm, setConfirm] = useState("");
  const [loading, setLoading] = useState(false);

  async function handleSubmit(event: React.FormEvent) {
    event.preventDefault();
    onError(null);
    if (password !== confirm) {
      onError("Passwords don't match");
      return;
    }
    setLoading(true);
    try {
      await api.post("/auth/password/reset", { token, new_password: password });
      router.push("/login");
    } catch (err) {
      onError(err instanceof ApiError ? String(err.detail) : "Could not reset password");
    } finally {
      setLoading(false);
    }
  }

  if (!token) {
    return <p className="mt-6 rounded-lg bg-danger-soft px-3 py-2 text-sm text-danger">This reset link is missing its token — request a new one.</p>;
  }

  return (
    <form onSubmit={handleSubmit}>
      <AuthField label="New password" type="password" required minLength={8} value={password} onChange={(e) => setPassword(e.target.value)} autoComplete="new-password" />
      <AuthField label="Confirm password" type="password" required minLength={8} value={confirm} onChange={(e) => setConfirm(e.target.value)} autoComplete="new-password" />
      <AuthButton disabled={loading}>{loading ? "Resetting…" : "Reset password"}</AuthButton>
    </form>
  );
}

export default function ResetPasswordPage() {
  const [error, setError] = useState<string | null>(null);
  return (
    <AuthShell title="Choose a new password" subtitle="Enter the new password for your account." error={error} footer={<AuthLink href="/login" strong>Back to sign in</AuthLink>}>
      <Suspense fallback={<p className="mt-6 text-sm text-white/75">Loading…</p>}>
        <ResetPasswordForm onError={setError} />
      </Suspense>
    </AuthShell>
  );
}
