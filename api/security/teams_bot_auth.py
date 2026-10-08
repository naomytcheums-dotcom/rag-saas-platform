"""Authentication of the inbound Microsoft Teams (Bot Framework) webhook.

Microsoft signs every activity it sends to a bot with an RS256 JWT: issuer `https://api.botframework.com`, audience = the bot's
Microsoft App ID, signed with a key published in the OpenID metadata at `TEAMS_OPENID_METADATA_URL`. This module checks that
token. Without it `POST /integrations/teams/webhook` would be open to anyone who knows a tenant id (not a secret) and could make
the platform run a paid RAG answer for that tenant.

The signing keys are fetched through `ssrf_safe_client()` (the one outbound-HTTP path this codebase allows) and cached; an unknown
`kid` forces one refresh, so a Microsoft key rotation is picked up without waiting for the cache to expire. Everything fails
CLOSED: no configured audience, no/ malformed header, wrong algorithm, issuer, audience, expiry or signature -> `TeamsAuthError`."""

import asyncio
import time

import jwt

from api.config import settings
from api.services.url_fetching import ssrf_safe_client

BOT_FRAMEWORK_ISSUER = "https://api.botframework.com"
_CLOCK_SKEW_SECONDS = 300

_cache: dict = {"keys": {}, "fetched_at": 0.0}
_lock = asyncio.Lock()


class TeamsAuthError(Exception):
    """The webhook caller could not be authenticated as Microsoft's Bot Framework."""


async def _fetch_jwks() -> dict[str, dict]:
    """kid -> JWK from the live OpenID metadata. Separate function so tests can replace the network call."""
    async with ssrf_safe_client(timeout=10.0) as client:
        metadata = (await client.get(settings.TEAMS_OPENID_METADATA_URL)).raise_for_status().json()
        keys = (await client.get(metadata["jwks_uri"])).raise_for_status().json()["keys"]
    return {key["kid"]: key for key in keys if "kid" in key}


async def _signing_key(kid: str):
    async with _lock:
        fresh = (time.monotonic() - _cache["fetched_at"]) < settings.TEAMS_JWKS_CACHE_SECONDS
        if not fresh or kid not in _cache["keys"]:
            try:
                _cache["keys"], _cache["fetched_at"] = await _fetch_jwks(), time.monotonic()
            except Exception as exc:  # noqa: BLE001 -- any failure to obtain the keys must refuse the request, never let it through
                raise TeamsAuthError("could not load the Bot Framework signing keys") from exc
        jwk = _cache["keys"].get(kid)
    if jwk is None:
        raise TeamsAuthError("unknown signing key")
    return jwt.PyJWK(jwk).key


async def verify_teams_bearer(authorization: str | None, audiences: list[str]) -> dict:
    """Validated claims of the `Authorization: Bearer <jwt>` header, or `TeamsAuthError`."""
    audiences = [a for a in audiences if a]
    if not audiences:
        raise TeamsAuthError("no Teams bot app id is configured")
    scheme, _, token = (authorization or "").partition(" ")
    if scheme.lower() != "bearer" or not token.strip():
        raise TeamsAuthError("missing bearer token")
    try:
        header = jwt.get_unverified_header(token.strip())
        if header.get("alg") != "RS256" or not header.get("kid"):
            raise TeamsAuthError("unexpected token header")
        key = await _signing_key(header["kid"])
        return jwt.decode(
            token.strip(), key, algorithms=["RS256"], audience=audiences, issuer=BOT_FRAMEWORK_ISSUER,
            options={"require": ["exp", "iss", "aud"]}, leeway=_CLOCK_SKEW_SECONDS,
        )
    except jwt.PyJWTError as exc:
        raise TeamsAuthError(f"invalid token: {type(exc).__name__}") from exc
