"use client";

import Link from "next/link";
import { useRouter } from "next/navigation";
import { useState } from "react";
import { ApiError, useAuth } from "@/lib/auth";
import { api } from "@/lib/api";

export default function LoginPage() {
  const router = useRouter();
  const { login } = useAuth();
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
      setError(err instanceof ApiError ? String(err.detail) : "Échec de la connexion");
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
      setError(err instanceof ApiError ? String(err.detail) : "Code invalide");
    } finally {
      setLoading(false);
    }
  }

  return (
    <div className="flex min-h-screen items-center justify-center bg-gradient-to-br from-orange-50 to-white px-4">
      <div className="w-full max-w-sm rounded-2xl border border-border bg-surface p-8 shadow-sm">
        <h1 className="mb-1 text-xl font-semibold text-foreground">Content de vous revoir</h1>
        <p className="mb-6 text-sm text-foreground-muted">Connectez-vous à votre compte RAG SaaS Platform.</p>

        {error && <p className="mb-4 rounded-lg bg-danger-soft px-3 py-2 text-sm text-danger">{error}</p>}

        {mfaToken ? (
          <form onSubmit={handleMfaSubmit} className="flex flex-col gap-3">
            <label className="text-sm text-foreground-muted">
              Code à deux facteurs
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
              {loading ? "Vérification…" : "Vérifier"}
            </button>
          </form>
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
            <label className="text-sm text-foreground-muted">
              Mot de passe
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
                Se souvenir de moi
              </label>
              <Link href="/forgot-password" className="text-accent hover:underline">Mot de passe oublié ?</Link>
            </div>
            <button type="submit" disabled={loading} className="mt-2 rounded-lg bg-accent px-4 py-2.5 text-sm font-medium text-white hover:bg-accent-hover disabled:opacity-50">
              {loading ? "Connexion…" : "Se connecter"}
            </button>
          </form>
        )}

        <p className="mt-6 text-center text-sm text-foreground-muted">
          Pas encore de compte ? <Link href="/register" className="font-medium text-accent hover:underline">Inscription</Link>
        </p>
      </div>
    </div>
  );
}
