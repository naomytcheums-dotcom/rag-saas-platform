export type OAuthFragment =
  | { kind: "session"; accessToken: string }
  | { kind: "mfa"; mfaToken: string; methods: string[] }
  | { kind: "none" };

/** Reads the URL fragment the API puts on its redirect to /oauth-callback (api/routers/oauth.py, enterprise_sso.py):
 * `#access_token=…&expires_in=…` after a completed sign-in, or `#mfa_required=true&mfa_token=…&methods=totp,webauthn`
 * when the account has a second factor. A fragment is never sent to a server, which is why tokens travel there. */
export function parseOAuthFragment(hash: string): OAuthFragment {
  const params = new URLSearchParams(hash.replace(/^#/, ""));
  const accessToken = params.get("access_token");
  if (accessToken) return { kind: "session", accessToken };
  const mfaToken = params.get("mfa_token");
  if (params.get("mfa_required") === "true" && mfaToken) {
    return { kind: "mfa", mfaToken, methods: (params.get("methods") ?? "").split(",").filter(Boolean) };
  }
  return { kind: "none" };
}
