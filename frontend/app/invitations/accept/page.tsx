"use client";

import { useRouter, useSearchParams } from "next/navigation";
import { Suspense, useState } from "react";
import AuthShell, { AuthButton, AuthField, AuthLink } from "@/components/auth/AuthShell";
import { api, ApiError } from "@/lib/api";

interface AcceptResponse {
  message: string;
  organization_id?: string;
  access_token?: string;
}

// MAP-001 -- the page the invitation e-mail links to (api/routers/invitations.py builds `/invitations/accept?token=…`). It used to be a
// 404. An existing account just accepts; a new invitee is asked for a name, a password and the terms (the API answers 400 until it has them).
function AcceptInvitationForm({ onError }: { onError: (message: string | null) => void }) {
  const router = useRouter();
  const token = useSearchParams().get("token") ?? "";
  const [needsAccount, setNeedsAccount] = useState(false);
  const [fullName, setFullName] = useState("");
  const [password, setPassword] = useState("");
  const [acceptTerms, setAcceptTerms] = useState(false);
  const [loading, setLoading] = useState(false);

  async function handleSubmit(event: React.FormEvent) {
    event.preventDefault();
    onError(null);
    setLoading(true);
    try {
      const body = needsAccount
        ? { token, password, full_name: fullName || null, accept_terms: acceptTerms }
        : { token };
      const result = await api.post<AcceptResponse>("/invitations/accept", body);
      if (result.access_token) {
        window.localStorage.setItem("access_token", result.access_token);
        window.location.replace("/dashboard");
      } else {
        router.push("/login");
      }
    } catch (err) {
      const detail = err instanceof ApiError ? String(err.detail) : "Could not accept the invitation";
      if (!needsAccount && err instanceof ApiError && err.status === 400 && /password is required/i.test(detail)) {
        setNeedsAccount(true);
      } else {
        onError(detail);
      }
    } finally {
      setLoading(false);
    }
  }

  if (!token) {
    return <p className="mt-6 rounded-lg bg-danger-soft px-3 py-2 text-sm text-danger">This invitation link is missing its token — ask for a new invitation.</p>;
  }

  return (
    <form onSubmit={handleSubmit}>
      {needsAccount && (
        <>
          <p className="mt-4 text-sm text-white/75">Create your account to join the organization.</p>
          <AuthField label="Full name" value={fullName} onChange={(e) => setFullName(e.target.value)} autoComplete="name" />
          <AuthField label="Password" type="password" required minLength={8} value={password} onChange={(e) => setPassword(e.target.value)} autoComplete="new-password" />
          <label className="mt-3 flex items-center gap-2 text-sm">
            <input type="checkbox" checked={acceptTerms} onChange={(e) => setAcceptTerms(e.target.checked)} />
            I accept the terms of service
          </label>
        </>
      )}
      <AuthButton disabled={loading || (needsAccount && (!password || !acceptTerms))}>{loading ? "Joining…" : needsAccount ? "Create account and join" : "Accept invitation"}</AuthButton>
    </form>
  );
}

export default function AcceptInvitationPage() {
  const [error, setError] = useState<string | null>(null);
  return (
    <AuthShell title="Join the organization" subtitle="You have been invited to collaborate." error={error} footer={<AuthLink href="/login" strong>Back to sign in</AuthLink>}>
      <Suspense fallback={<p className="mt-6 text-sm text-white/75">Loading…</p>}>
        <AcceptInvitationForm onError={setError} />
      </Suspense>
    </AuthShell>
  );
}
