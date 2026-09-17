"""
Audit finding 26 -- WebAuthn/FIDO2 as a second factor, alongside (never
instead of) TOTP: api/routers/webauthn.py's registration/authentication
endpoints, api/models/webauthn_credential.py's storage. Backed by the
`webauthn` PyPI package (py_webauthn) -- pure Python plus `cryptography`
(already a dependency, see requirements-api.txt), no native/system
library needed (unlike a SAML implementation, see
api/models/enterprise_sso.py's docstring for that same reasoning applied
to item 27).

Challenge storage: a WebAuthn ceremony is two round trips (options, then
a signed response) and the server must remember the exact random
challenge it issued to reject a replayed/forged response -- stored in
Redis (this app's existing ephemeral-state store, already relied on by
api/security/rate_limit.py) with a short TTL, deleted the moment it's
consumed so a challenge can never be reused even if a request is
replayed. A dedicated connection, not api/security/rate_limit.py's
private client, same reasoning as api/security/geoip.py's own module-level
client (avoids an import cycle; the two modules have no other reason to
know about each other).
"""

import asyncio
import logging

import redis.asyncio as redis_asyncio
import webauthn
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from webauthn.helpers.structs import (
    AttestationConveyancePreference,
    AuthenticatorSelectionCriteria,
    PublicKeyCredentialDescriptor,
    ResidentKeyRequirement,
    UserVerificationRequirement,
)

from api.config import settings
from api.models.webauthn_credential import WebAuthnCredential
from api.security.redis_client import get_or_rebuild

logger = logging.getLogger(__name__)

# Same real timeout fix as api/security/rate_limit.py's own _redis --
# see that module's comment for the full incident.
#
# Same loop-rebinding fix as api/security/rate_limit.py's _get_redis()
# too -- see that module's comment for the full "Event loop is closed"
# incident, and api/security/redis_client.py for the shared rebuild
# logic. This module has its own separate client (a dedicated global,
# not rate_limit.py's), so it needs its own separate accessor -- but
# the actual rebuild-on-loop-mismatch logic is shared, not copy-pasted.
_redis: redis_asyncio.Redis | None = None
_redis_loop: asyncio.AbstractEventLoop | None = None
_CHALLENGE_TTL_SECONDS = 300  # matches MFA_TOKEN_EXPIRE_MINUTES's ballpark (settings.py) -- long enough for a real ceremony, short enough to bound a replay window


def _get_redis() -> redis_asyncio.Redis:
    global _redis, _redis_loop
    _redis, _redis_loop = get_or_rebuild(
        _redis, _redis_loop, settings.RATE_LIMIT_REDIS_URL,
        decode_responses=True, socket_connect_timeout=3.0, socket_timeout=1.0,
    )
    return _redis


def _registration_challenge_key(user_id) -> str:
    return f"webauthn:challenge:register:{user_id}"


def _authentication_challenge_key(mfa_token_hash: str) -> str:
    return f"webauthn:challenge:authenticate:{mfa_token_hash}"


async def _store_challenge(key: str, challenge: bytes) -> None:
    await _get_redis().set(key, webauthn.helpers.bytes_to_base64url(challenge), ex=_CHALLENGE_TTL_SECONDS)


async def _pop_challenge(key: str) -> bytes | None:
    """Reads AND deletes in one step (Redis GETDEL) -- a challenge is
    single-use by construction, never valid for a second verify attempt
    even if the first one failed."""
    encoded = await _get_redis().getdel(key)
    return webauthn.helpers.base64url_to_bytes(encoded) if encoded else None


def _credential_descriptor(cred: WebAuthnCredential) -> PublicKeyCredentialDescriptor:
    return PublicKeyCredentialDescriptor(id=cred.credential_id)


async def get_user_credentials(db: AsyncSession, user_id) -> list[WebAuthnCredential]:
    """Shared by api/routers/webauthn.py (registration/management) AND
    api/routers/auth.py + oauth.py's login flows (to decide whether
    WebAuthn is one of this account's available second factors,
    alongside TOTP) -- kept here rather than duplicated in each router,
    same reason api/security/sessions.py's helpers are shared across
    auth.py/oauth.py/two_factor.py."""
    return (await db.scalars(select(WebAuthnCredential).where(WebAuthnCredential.user_id == user_id))).all()


async def build_registration_options(user_id, user_email: str, existing_credentials: list[WebAuthnCredential]) -> bytes:
    """
    Step 1 of registering a new physical key/authenticator -- generates a
    fresh random challenge, stores it (keyed by user, so a second
    concurrent registration attempt for the same user overwrites rather
    than stacks -- only the most recent one is honored), and returns the
    options JSON exactly as `navigator.credentials.create()` expects it.

    exclude_credentials lists every credential this user already has, so
    the browser/authenticator can refuse to re-register the SAME physical
    key twice (a native WebAuthn behavior, not something this app has to
    check for itself at verify time).
    """
    options = webauthn.generate_registration_options(
        rp_id=settings.WEBAUTHN_RP_ID,
        rp_name=settings.WEBAUTHN_RP_NAME,
        user_id=str(user_id).encode(),
        user_name=user_email,
        attestation=AttestationConveyancePreference.NONE,
        authenticator_selection=AuthenticatorSelectionCriteria(
            resident_key=ResidentKeyRequirement.DISCOURAGED,
            user_verification=UserVerificationRequirement.PREFERRED,
        ),
        exclude_credentials=[_credential_descriptor(c) for c in existing_credentials],
    )
    await _store_challenge(_registration_challenge_key(user_id), options.challenge)
    return webauthn.options_to_json(options).encode()


async def verify_registration(user_id, credential) -> webauthn.registration.verify_registration_response.VerifiedRegistration:
    """
    Step 2: verifies the browser's attestation response against the
    challenge stored by build_registration_options -- raises
    webauthn.helpers.exceptions.InvalidRegistrationResponse (or a more
    specific subclass) on any failure, including "no challenge found"
    (a None expected_challenge fails verification cleanly rather than
    needing its own special-cased check here).
    """
    challenge = await _pop_challenge(_registration_challenge_key(user_id))
    return webauthn.verify_registration_response(
        credential=credential,
        expected_challenge=challenge or b"",
        expected_rp_id=settings.WEBAUTHN_RP_ID,
        expected_origin=settings.WEBAUTHN_RP_ORIGIN,
    )


async def build_authentication_options(mfa_token_hash: str, credentials: list[WebAuthnCredential]) -> bytes:
    """
    Step 1 of the login-time second factor -- parallels
    api/routers/two_factor.py's /verify-login, but for a physical key
    instead of a 6-digit code. allow_credentials narrows the browser's
    prompt to only the keys THIS account actually registered (rather than
    "any key you have," which would leak nothing sensitive but would be a
    worse UX and isn't how a real login screen would want to behave).

    Challenge keyed by the HASHED mfa_token, not the user id -- the
    caller only has a pending-login token at this point, same "never key
    anything on the raw token value" reasoning as every rate-limit key in
    this codebase (api/security/rate_limit.py, api/routers/two_factor.py).
    """
    options = webauthn.generate_authentication_options(
        rp_id=settings.WEBAUTHN_RP_ID,
        allow_credentials=[_credential_descriptor(c) for c in credentials],
        user_verification=UserVerificationRequirement.PREFERRED,
    )
    await _store_challenge(_authentication_challenge_key(mfa_token_hash), options.challenge)
    return webauthn.options_to_json(options).encode()


async def verify_authentication(
    mfa_token_hash: str, credential, stored_credential: WebAuthnCredential
) -> webauthn.authentication.verify_authentication_response.VerifiedAuthentication:
    """
    Step 2: verifies the assertion against BOTH the challenge stored by
    build_authentication_options AND the specific credential's stored
    public key + sign count. Raises on a bad signature, a missing/expired
    challenge, OR a sign-count regression (webauthn's own
    InvalidAuthenticationResponse family) -- the last of those is this
    library's built-in defense against a cloned authenticator: a
    legitimate physical key's internal counter only ever increases, so a
    lower-or-equal count presented later means two physical copies of the
    same credential exist, which should never happen.
    """
    challenge = await _pop_challenge(_authentication_challenge_key(mfa_token_hash))
    return webauthn.verify_authentication_response(
        credential=credential,
        expected_challenge=challenge or b"",
        expected_rp_id=settings.WEBAUTHN_RP_ID,
        expected_origin=settings.WEBAUTHN_RP_ORIGIN,
        credential_public_key=stored_credential.public_key,
        credential_current_sign_count=stored_credential.sign_count,
    )
