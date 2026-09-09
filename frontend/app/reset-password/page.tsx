"use client";

import Link from "next/link";
import { useRouter, useSearchParams } from "next/navigation";
import { Suspense, useState } from "react";
import { api, ApiError } from "@/lib/api";

function ResetPasswordForm() {
  const router = useRouter();
  const token = useSearchParams().get("token") ?? "";
  const [password, setPassword] = useState("");
  const [confirm, setConfirm] = useState("");
  const [error, setError] = useState<string | null>(null);
  const [loading, setLoading] = useState(false);

  async function handleSubmit(event: React.FormEvent) {
    event.preventDefault();
    setError(null);
    if (password !== confirm) {
      setError("Passwords don't match");
      return;
    }
    setLoading(true);
    try {
      await api.post("/auth/password/reset", { token, new_password: password });
      router.push("/login");
    } catch (err) {
      setError(err instanceof ApiError ? String(err.detail) : "Could not reset password");
    } finally {
      setLoading(false);
    }
  }

  if (!token) {
    return <p className="rounded-lg bg-danger-soft px-3 py-2 text-sm text-danger">This reset link is missing its token — request a new one.</p>;
  }

  return (
    <form onSubmit={handleSubmit} className="flex flex-col gap-3">
      {error && <p className="rounded-lg bg-danger-soft px-3 py-2 text-sm text-danger">{error}</p>}
      <label className="text-sm text-foreground-muted">
        New password
        <input
          type="password"
          required
          minLength={8}
          value={password}
          onChange={(e) => setPassword(e.target.value)}
          className="mt-1 w-full rounded-lg border border-border bg-background px-3 py-2 text-sm outline-none focus:border-accent"
        />
      </label>
      <label className="text-sm text-foreground-muted">
        Confirm password
        <input
          type="password"
          required
          minLength={8}
          value={confirm}
          onChange={(e) => setConfirm(e.target.value)}
          className="mt-1 w-full rounded-lg border border-border bg-background px-3 py-2 text-sm outline-none focus:border-accent"
        />
      </label>
      <button type="submit" disabled={loading} className="mt-2 rounded-lg bg-accent px-4 py-2.5 text-sm font-medium text-white hover:bg-accent-hover disabled:opacity-50">
        {loading ? "Resetting…" : "Reset password"}
      </button>
    </form>
  );
}

export default function ResetPasswordPage() {
  return (
    <div className="flex min-h-screen items-center justify-center bg-gradient-to-br from-orange-50 to-white px-4">
      <div className="w-full max-w-sm rounded-2xl border border-border bg-surface p-8 shadow-sm">
        <h1 className="mb-1 text-xl font-semibold text-foreground">Choose a new password</h1>
        <p className="mb-6 text-sm text-foreground-muted">Enter the new password for your account.</p>

        <Suspense fallback={<p className="text-sm text-foreground-muted">Loading…</p>}>
          <ResetPasswordForm />
        </Suspense>

        <p className="mt-6 text-center text-sm text-foreground-muted">
          <Link href="/login" className="font-medium text-accent hover:underline">Back to sign in</Link>
        </p>
      </div>
    </div>
  );
}
