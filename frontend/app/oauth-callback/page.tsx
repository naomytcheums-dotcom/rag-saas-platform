"use client";

import { useEffect, useState } from "react";
import AuthShell, { AuthButton, AuthField, AuthLink } from "@/components/auth/AuthShell";
import { api, ApiError } from "@/lib/api";
import { parseOAuthFragment } from "@/lib/oauth-callback";

type View = { kind: "working" } | { kind: "mfa"; mfaToken: string } | { kind: "error"; message: string };

function finishSignIn(accessToken: string) {
  window.localStorage.setItem("access_token", accessToken);
  // A full navigation so that the auth provider reads the new session from scratch.
  window.location.replace("/dashboard");
}

// MAP-002 -- the page the API redirects to after Google/GitHub/enterprise SSO (api/routers/oauth.py, enterprise_sso.py). It used to
// be a 404, so an OAuth/SSO sign-in could never complete in the interface.
export default function OAuthCallbackPage() {
  const [view, setView] = useState<View>({ kind: "working" });
  const [code, setCode] = useState("");
  const [useRecovery, setUseRecovery] = useState(false);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    const fragment = parseOAuthFragment(window.location.hash);
    // Keep the token out of the address bar and the browser history as soon as it has been read.
    window.history.replaceState(null, "", window.location.pathname);
    if (fragment.kind === "session") {
      finishSignIn(fragment.accessToken);
    } else if (fragment.kind === "mfa") {
      // eslint-disable-next-line react-hooks/set-state-in-effect -- justified: reading the URL fragment (an external browser value) once after mount.
      setView({ kind: "mfa", mfaToken: fragment.mfaToken });
    } else {
      setView({ kind: "error", message: "This sign-in link is incomplete or has already been used. Please sign in again." });
    }
  }, []);

  async function handleSubmit(event: React.FormEvent) {
    event.preventDefault();
    if (view.kind !== "mfa") return;
    setLoading(true);
    setError(null);
    try {
      const path = useRecovery ? "/auth/2fa/verify-recovery-code" : "/auth/2fa/verify-login";
      const body = useRecovery ? { mfa_token: view.mfaToken, recovery_code: code } : { mfa_token: view.mfaToken, code };
      const result = await api.post<{ access_token: string }>(path, body);
      finishSignIn(result.access_token);
    } catch (err) {
      setError(err instanceof ApiError ? String(err.detail) : "Could not verify the code");
    } finally {
      setLoading(false);
    }
  }

  if (view.kind === "error") {
    return (
      <AuthShell title="Sign-in problem" subtitle={view.message} footer={<AuthLink href="/login" strong>Back to sign in</AuthLink>}>
        <span />
      </AuthShell>
    );
  }

  if (view.kind === "mfa") {
    return (
      <AuthShell
        title="Two-factor authentication"
        subtitle={useRecovery ? "Enter one of your single-use recovery codes." : "Enter the 6-digit code from your authenticator app."}
        error={error}
        footer={<AuthLink href="/login">Cancel</AuthLink>}
      >
        <form onSubmit={handleSubmit}>
          <AuthField
            label={useRecovery ? "Recovery code" : "Authentication code"} required value={code} onChange={(e) => setCode(e.target.value)}
            autoComplete="one-time-code" inputMode={useRecovery ? "text" : "numeric"} maxLength={useRecovery ? 64 : 6}
          />
          <AuthButton disabled={loading || !code}>{loading ? "Verifying…" : "Verify"}</AuthButton>
        </form>
        <button
          type="button" className="mt-4 text-sm underline"
          onClick={() => { setUseRecovery((value) => !value); setCode(""); setError(null); }}
        >
          {useRecovery ? "Use my authenticator app instead" : "Use a recovery code instead"}
        </button>
      </AuthShell>
    );
  }

  return <AuthShell title="Signing you in…" subtitle="One moment."><span /></AuthShell>;
}
