"use client";

import { useSearchParams } from "next/navigation";
import { Suspense, useState } from "react";
import AuthShell, { AuthButton, AuthLink } from "@/components/auth/AuthShell";
import { api, ApiError } from "@/lib/api";

interface MessageResponse {
  message: string;
}

interface Props {
  title: string;
  subtitle: string;
  endpoint: string;
  button: string;
  busy: string;
  missingToken: string;
  /** Consent has to be given again (GDPR): the confirmation is only sent once the box is ticked, with `accept_terms: true`. */
  termsLabel?: string;
}

// The page an e-mailed link opens (MAP-003). Nothing is sent when the page loads (a mail scanner or a link preview must not confirm
// anything): the user presses the button, and only then is the token posted to the API.
function TokenConfirmation({ endpoint, button, busy, missingToken, termsLabel, onError }: Omit<Props, "title" | "subtitle"> & { onError: (message: string | null) => void }) {
  const token = useSearchParams().get("token") ?? "";
  const [acceptTerms, setAcceptTerms] = useState(false);
  const [loading, setLoading] = useState(false);
  const [done, setDone] = useState<string | null>(null);

  async function handleSubmit(event: React.FormEvent) {
    event.preventDefault();
    onError(null);
    setLoading(true);
    try {
      const body = termsLabel ? { token, accept_terms: acceptTerms } : { token };
      const result = await api.post<MessageResponse>(endpoint, body);
      setDone(result.message);
    } catch (err) {
      onError(err instanceof ApiError ? String(err.detail) : "This link could not be confirmed");
    } finally {
      setLoading(false);
    }
  }

  if (!token) {
    return <p className="mt-6 rounded-lg bg-danger-soft px-3 py-2 text-sm text-danger">{missingToken}</p>;
  }
  if (done) {
    return <p role="status" className="mt-6 text-center text-sm">{done}</p>;
  }

  return (
    <form onSubmit={handleSubmit}>
      {termsLabel && (
        <label className="mt-6 flex items-center gap-2 text-sm">
          <input type="checkbox" checked={acceptTerms} onChange={(e) => setAcceptTerms(e.target.checked)} />
          {termsLabel}
        </label>
      )}
      <AuthButton disabled={loading || (Boolean(termsLabel) && !acceptTerms)}>{loading ? busy : button}</AuthButton>
    </form>
  );
}

export default function TokenConfirmForm({ title, subtitle, ...props }: Props) {
  const [error, setError] = useState<string | null>(null);
  return (
    <AuthShell title={title} subtitle={subtitle} error={error} footer={<AuthLink href="/login" strong>Back to sign in</AuthLink>}>
      <Suspense fallback={<p className="mt-6 text-sm text-white/75">Loading…</p>}>
        <TokenConfirmation {...props} onError={setError} />
      </Suspense>
    </AuthShell>
  );
}
