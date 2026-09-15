"use client";

import Link from "next/link";
import { useRouter } from "next/navigation";
import { useState } from "react";
import { ApiError, useAuth } from "@/lib/auth";

export default function RegisterPage() {
  const router = useRouter();
  const { register } = useAuth();
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
      setError(err instanceof ApiError ? String(err.detail) : "Échec de l'inscription");
    } finally {
      setLoading(false);
    }
  }

  return (
    <div className="flex min-h-screen items-center justify-center bg-gradient-to-br from-orange-50 to-white px-4">
      <div className="w-full max-w-sm rounded-2xl border border-border bg-surface p-8 shadow-sm">
        <h1 className="mb-1 text-xl font-semibold text-foreground">Créez votre compte</h1>
        <p className="mb-6 text-sm text-foreground-muted">Commencez à construire avec RAG SaaS Platform.</p>

        {error && <p className="mb-4 rounded-lg bg-danger-soft px-3 py-2 text-sm text-danger">{error}</p>}

        <form onSubmit={handleSubmit} className="flex flex-col gap-3">
          <label className="text-sm text-foreground-muted">
            Nom complet
            <input
              type="text"
              value={fullName}
              onChange={(e) => setFullName(e.target.value)}
              className="mt-1 w-full rounded-lg border border-border bg-background px-3 py-2 text-sm outline-none focus:border-accent"
              placeholder="Ada Lovelace"
            />
          </label>
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
          <label className="text-sm text-foreground-muted">
            Mot de passe
            <input
              type="password"
              required
              minLength={8}
              value={password}
              onChange={(e) => setPassword(e.target.value)}
              className="mt-1 w-full rounded-lg border border-border bg-background px-3 py-2 text-sm outline-none focus:border-accent"
              placeholder="Au moins 8 caractères"
            />
          </label>
          <button type="submit" disabled={loading} className="mt-2 rounded-lg bg-accent px-4 py-2.5 text-sm font-medium text-white hover:bg-accent-hover disabled:opacity-50">
            {loading ? "Création du compte…" : "Créer le compte"}
          </button>
        </form>

        <p className="mt-6 text-center text-sm text-foreground-muted">
          Déjà un compte ? <Link href="/login" className="font-medium text-accent hover:underline">Se connecter</Link>
        </p>
      </div>
    </div>
  );
}
