"""Shared FastAPI dependencies: DB session (re-exported for convenience) and
the current-user resolvers every protected route depends on."""

import asyncio
import logging

from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from jwt import ExpiredSignatureError, InvalidTokenError
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from api.config import settings
from api.database import get_db
from api.models.audit_log import AuditAction
from api.models.revoked_token import RevokedAccessToken
from api.models.user import User, UserRole
from api.security.audit_log import log_audit_action
from api.security.jwt import InvalidTokenPurposeError, TokenPurpose, decode_token
from api.security.sessions import revoke_session, touch_session_and_check_idle_timeout
from api.services.email import send_idle_session_revoked_email

logger = logging.getLogger(__name__)

__all__ = ["get_db", "get_current_user", "get_current_user_any_consent_status", "require_admin", "require_superadmin"]

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

    # Audit findings 13/17: refreshes the paired Session's last_seen_at,
    # and enforces SESSION_IDLE_TIMEOUT_MINUTES in the same round trip
    # (see touch_session_and_check_idle_timeout's own docstring). A
    # non-None return means the session WAS active but has been idle too
    # long -- revoked here (blacklisting its access token, same as any
    # other revocation) and the request rejected, rather than silently
    # let it through this one last time.
    idle_session = await touch_session_and_check_idle_timeout(db, decoded.jti)
    if idle_session is not None:
        notify_email = await db.scalar(select(User.email).where(User.id == idle_session.user_id))
        await revoke_session(db, idle_session)
        await log_audit_action(
            db, user_id=idle_session.user_id, action=AuditAction.SESSION_IDLE_TIMEOUT, ip=None, user_agent=None,
            success=True, metadata={"session_id": str(idle_session.id)},
        )
        await db.commit()
        if notify_email:
            try:
                await asyncio.to_thread(send_idle_session_revoked_email, notify_email)
            except (EnvironmentError, RuntimeError) as exc:
                logger.warning("failed to send idle-timeout notification to %s: %s", notify_email, exc)
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


async def require_admin(user: User = Depends(get_current_user)) -> User:
    """
    Audit findings 19/20 -- gates GET /admin/audit-logs and
    GET /admin/failed-logins. Layered on top of get_current_user (not
    get_current_user_any_consent_status): an admin still has to be a
    fully-in-good-standing user first (current terms accepted, etc.) --
    admin access isn't a bypass of the ordinary account gates, it's an
    additional check on top of them. 404, not 403, for a non-admin: an
    admin-only endpoint's mere existence isn't information a regular
    authenticated user needs, the same reasoning DELETE /sessions/{id}
    already uses for a session belonging to someone else.
    """
    if user.role not in (UserRole.admin, UserRole.superadmin):
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Not found")
    return user


async def require_superadmin(user: User = Depends(get_current_user)) -> User:
    """
    Etape 1.2.1 -- Super Admin: the single highest privilege tier,
    strictly narrower than require_admin above (which also accepts a
    plain admin). Gates the first genuinely superadmin-exclusive
    capability, PATCH /admin/users/{id}/role (api/routers/admin_users.py) --
    granting or revoking admin/superadmin access is more consequential
    than anything require_admin gates today (reading audit logs,
    configuring SSO), so it gets a stricter check of its own rather than
    reusing require_admin.

    Deliberately checks User.role == UserRole.superadmin -- the EXISTING
    enum column (added by migration 0010) -- rather than a separate
    is_superadmin boolean. Migration 0010 already removed exactly that
    boolean column in favor of this enum, specifically because a boolean
    can only ever represent two tiers; reintroducing it now would
    recreate two sources of truth for the same fact (role == "superadmin"
    vs is_superadmin == True) that could silently drift apart from each
    other with no constraint stopping it.

    403, not 404 (unlike require_admin): the reasoning that justifies
    404 there -- a regular end user has no reason to even learn
    admin-only routes exist -- doesn't carry over the same way here.
    Anyone who can reach this dependency at all is already an
    authenticated admin or superadmin; an admin discovering that a
    stricter tier exists above them is a far smaller information leak
    than an ordinary user discovering admin routes exist in the first
    place.
    """
    if user.role != UserRole.superadmin:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Superadmin access required")
    return user
