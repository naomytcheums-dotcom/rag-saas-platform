"use client";

import Link from "next/link";
import { useState } from "react";
import { api, ApiError } from "@/lib/api";

export default function ForgotPasswordPage() {
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
      setError(err instanceof ApiError ? String(err.detail) : "Une erreur est survenue");
    } finally {
      setLoading(false);
    }
  }

  return (
    <div className="flex min-h-screen items-center justify-center bg-gradient-to-br from-orange-50 to-white px-4">
      <div className="w-full max-w-sm rounded-2xl border border-border bg-surface p-8 shadow-sm">
        <h1 className="mb-1 text-xl font-semibold text-foreground">Réinitialiser votre mot de passe</h1>
        <p className="mb-6 text-sm text-foreground-muted">Nous vous enverrons un vrai lien de réinitialisation par email.</p>

        {error && <p className="mb-4 rounded-lg bg-danger-soft px-3 py-2 text-sm text-danger">{error}</p>}

        {sent ? (
          <p className="rounded-lg bg-success-soft px-3 py-2 text-sm text-success">
            Si un compte existe pour cet email, un lien de réinitialisation a été envoyé.
          </p>
        ) : (
          <form onSubmit={handleSubmit} className="flex flex-col gap-3">
            <label className="text-sm text-foreground-muted">
              Email
              <input
                type="email"
                required
                value={email}
                onChange={(e) => setEmail(e.target.value)}
                className="mt-1 w-full rounded-lg border border-border bg-background px-3 py-2 text-sm outline-none focus:border-accent"
                placeholder="vous@exemple.com"
              />
            </label>
            <button type="submit" disabled={loading} className="mt-2 rounded-lg bg-accent px-4 py-2.5 text-sm font-medium text-white hover:bg-accent-hover disabled:opacity-50">
              {loading ? "Envoi…" : "Envoyer le lien"}
            </button>
          </form>
        )}

        <p className="mt-6 text-center text-sm text-foreground-muted">
          <Link href="/login" className="font-medium text-accent hover:underline">Retour à la connexion</Link>
        </p>
      </div>
    </div>
  );
}
