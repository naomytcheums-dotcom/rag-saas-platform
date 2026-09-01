"""Shared FastAPI dependencies: DB session (re-exported for convenience) and
the current-user resolvers every protected route depends on."""

from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from jwt import ExpiredSignatureError, InvalidTokenError
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from api.config import settings
from api.database import get_db
from api.models.revoked_token import RevokedAccessToken
from api.models.user import User
from api.security.jwt import InvalidTokenPurposeError, TokenPurpose, decode_token

__all__ = ["get_db", "get_current_user", "get_current_user_any_consent_status"]

_bearer_scheme = HTTPBearer(description="Access token from POST /auth/login or /auth/refresh")

STALE_TERMS_DETAIL = "You must accept the updated terms of service to continue -- POST /account/consent/accept-updated-terms"


async def get_current_user_any_consent_status(
    credentials: HTTPAuthorizationCredentials = Depends(_bearer_scheme),
    db: AsyncSession = Depends(get_db),
) -> User:
    """
    Identity/active/blacklist checks ONLY -- no terms-freshness check
    (see get_current_user below for that, and why this lower-level
    version exists at all). Reads the `Authorization: Bearer <token>`
    header via the HTTPBearer scheme above, decodes it as an
    access-purpose JWT, checks it against the revocation blacklist
    (1.1.15, api/models/revoked_token.py), and loads the matching user
    row. Any failure along the way -- missing header, malformed/expired/
    revoked token, or a user that no longer exists/is deactivated/
    soft-deleted -- collapses to the same generic 401, so a caller can't
    distinguish "your token is fine but your account was deleted" from
    "your token was revoked" from "your token is garbage."

    Cost of revocability, stated plainly: this is now one extra indexed
    DB read on every single authenticated request, where before this was
    pure CPU (decode + verify a signature, nothing else). That's the
    trade-off "an access token must actually be revocable, not just
    short-lived" requires -- a stateless JWT and a revocable one are
    mutually exclusive properties. The `jti` blacklist table
    (api/models/revoked_token.py) stays small in practice (Celery purges
    rows once their underlying token would have expired anyway, see
    api/tasks/token_blacklist_cleanup.py), and the lookup is a unique
    index hit, not a scan.

    Used directly (instead of get_current_user) only by the small,
    deliberate set of routes that must stay reachable even for an
    account that hasn't accepted updated terms yet: the RGPD rights
    themselves (GET /account/export, DELETE /account/me,
    POST /account/consent/withdraw -- you can't hold someone's own
    rights hostage to them accepting NEW terms first), basic session
    security (GET/DELETE /sessions -- a user must always be able to see
    or kill their own sessions), 2FA account security (POST /auth/2fa/setup,
    /enable, /disable, /recovery-codes/regenerate, and
    GET /recovery-codes/status -- same reasoning as sessions: each already
    requires either no prior 2FA state or a valid current TOTP code, so
    turning 2FA on/off or rotating recovery codes can't be held hostage to
    accepting new terms either), GET /account/me (so a frontend can at
    least read enough to show the "please accept updated terms" prompt),
    and POST /account/consent/accept-updated-terms itself (the one
    endpoint that fixes the problem -- it obviously can't require the
    problem to already be fixed to be reachable).
    """
    unauthorized = HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid or expired access token")

    try:
        decoded = decode_token(credentials.credentials, TokenPurpose.ACCESS)
    except (ExpiredSignatureError, InvalidTokenError, InvalidTokenPurposeError):
        raise unauthorized

    is_revoked = await db.scalar(select(RevokedAccessToken.id).where(RevokedAccessToken.jti == decoded.jti).limit(1))
    if is_revoked is not None:
        raise unauthorized

    user = await db.scalar(select(User).where(User.id == decoded.user_id))
    if user is None or not user.is_active or user.is_deleted:
        raise unauthorized
    return user


async def get_current_user(user: User = Depends(get_current_user_any_consent_status)) -> User:
    """
    The dependency every ordinary protected route uses. Everything
    get_current_user_any_consent_status already checks, PLUS (1.1.12/4.3):
    if TERMS_VERSION has changed since this user last consented, they're
    blocked with 403 (not the generic 401 -- this is a real, authenticated
    user, just not currently allowed to use the service) until they
    accept the new terms via POST /account/consent/accept-updated-terms.

    user.terms_version is None only for a genuinely never-consented row,
    which should not exist for any account that can reach this dependency
    at all (register() and OAuth sign-up both backfill it, see
    api/routers/auth.py and api/routers/oauth.py) -- but None is treated
    as "stale" rather than silently passed, since a real account somehow
    missing this record is exactly the case RGPD compliance can't quietly
    ignore either.
    """
    if user.terms_version != settings.TERMS_VERSION:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail=STALE_TERMS_DETAIL)
    return user
