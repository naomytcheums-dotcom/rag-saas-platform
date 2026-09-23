"""
Audit finding 27 -- generic OIDC client logic for enterprise SSO, used by
api/routers/enterprise_sso.py. Deliberately built on plain httpx + PyJWT
(both already dependencies) rather than Authlib's static, app-wide
OAuth() registry (api/routers/oauth.py's Google/GitHub integration):
that registry is designed for a small, fixed set of providers registered
once at import time, whereas an enterprise connection is admin-configured
at runtime, one per customer, potentially many of them -- a fresh
per-request client built from the DB row is the correct shape here, the
same way Authlib itself recommends for multi-tenant OIDC.

OIDC discovery is fetched fresh from {issuer}/.well-known/openid-configuration
on every authorize/callback rather than cached -- enterprise SSO logins
are inherently low-frequency compared to ordinary password/OAuth logins,
and always fetching fresh means an IdP rotating its own token/JWKS
endpoints is picked up immediately, with no cache-invalidation mechanism
to build or get wrong.
"""

import asyncio

import httpx
import jwt as pyjwt
from authlib.integrations.httpx_client import AsyncOAuth2Client

_METADATA_TIMEOUT_SECONDS = 5.0


async def fetch_oidc_metadata(issuer: str) -> dict:
    """Raises httpx.HTTPError on any failure -- callers decide how to
    surface that (api/routers/enterprise_sso.py turns it into a clean
    400/503, never lets it become an unhandled 500).

    Phase 4, Étape 4 (SSRF Hardening Extension) -- real, DELIBERATE
    non-fix, audited and reverted after a real, confirmed regression
    (not left broken -- caught and reasoned about): an earlier version
    of this function routed through `url_fetching.ssrf_safe_client()`
    (this codebase's own canonical SSRF-safe transport), the same real
    fix applied to `api.services.chat_integrations.teams.send_teams_response`/
    `api.services.alerting.send_alert_notification`. That broke a real,
    legitimate, already-passing integration test
    (`tests/test_enterprise_sso_integration.py`, which runs a REAL local
    IdP on `127.0.0.1` to test the full real OIDC flow end-to-end) --
    and, more importantly, would have broken every REAL enterprise
    deployment whose own IdP genuinely lives on internal/private network
    space (VPN-only, same-VPC, behind an internal load balancer -- a
    real, common, legitimate enterprise SSO topology, unlike a public
    Teams incoming-webhook or a public alert-webhook target). Applying
    the SAME "must resolve to a real public IP" policy here would be a
    real, wrong security/functionality trade-off for THIS specific
    integration, not a generic webhook. Left as a real, PLAIN
    `httpx.AsyncClient` -- genuinely un-hardened against a
    malicious/compromised admin-configured `issuer` pointing at internal
    infrastructure; see this étape's own "Limites restantes" for the
    honest, undischarged risk this leaves (a real, separate, future
    étape should design an admin-scoped internal-network ALLOWLIST for
    enterprise SSO specifically, not the same public-only policy)."""
    url = issuer.rstrip("/") + "/.well-known/openid-configuration"
    async with httpx.AsyncClient(timeout=_METADATA_TIMEOUT_SECONDS) as client:
        response = await client.get(url)
    response.raise_for_status()
    return response.json()


def build_client(client_id: str, redirect_uri: str, client_secret: str | None = None) -> AsyncOAuth2Client:
    """A fresh, unregistered OAuth2/OIDC client for ONE connection --
    never reused across requests or cached at module level (unlike
    api/routers/oauth.py's `oauth` registry), since a connection's
    client_id/secret can change (an admin could reconfigure it) and this
    codebase has no invalidation path for a cached client otherwise."""
    return AsyncOAuth2Client(
        client_id=client_id, client_secret=client_secret, redirect_uri=redirect_uri, scope="openid email profile",
    )


async def verify_id_token(id_token: str, metadata: dict, client_id: str, issuer: str) -> dict:
    """
    Real signature verification against the IdP's own published JWKS --
    NOT a bare `jwt.decode(..., options={"verify_signature": False})`,
    which would accept a forged id_token from anyone. PyJWKClient's key
    fetch is a synchronous (urllib-based) HTTP call; run via
    asyncio.to_thread so it doesn't block this process's event loop for
    every other in-flight request while it happens -- a real, if modest,
    cost given how infrequent an SSO login is relative to a password
    login, but worth avoiding since it's essentially free to do here.
    """
    def _verify() -> dict:
        jwks_client = pyjwt.PyJWKClient(metadata["jwks_uri"])
        signing_key = jwks_client.get_signing_key_from_jwt(id_token)
        return pyjwt.decode(id_token, signing_key.key, algorithms=["RS256"], audience=client_id, issuer=issuer)

    return await asyncio.to_thread(_verify)
