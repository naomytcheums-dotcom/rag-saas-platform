"""
Shared session issuance/rotation/revocation logic (1.1.8, 1.1.9, 1.1.15),
used by every router that can end with a logged-in user: auth.py
(register/login), oauth.py (OAuth callbacks), two_factor.py (the
post-MFA login step).

Kept out of auth.py itself so oauth.py and two_factor.py don't have to
import "auth" to get it -- this is genuinely shared infrastructure, not
auth.py's private implementation detail.
"""

import datetime as dt
import logging
import uuid

from fastapi import Request, Response
from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession

from api.config import settings
from api.models.audit_log import AuditAction
from api.models.revoked_token import RevokedAccessToken
from api.models.session import Session
from api.models.user import User
from api.schemas.auth import TokenResponse
from api.security.audit_log import log_audit_action
from api.security.csrf import generate_csrf_token, set_csrf_cookie
from api.security.hashing import generate_raw_token, hash_token
from api.security.jwt import create_access_token
from api.services.email import send_concurrent_session_limit_reached_email, send_new_login_notification_email
from api.utils import client_ip

logger = logging.getLogger(__name__)

REFRESH_COOKIE_NAME = "refresh_token"
# "/" rather than "/auth": GET/DELETE /sessions (1.1.9, a different router)
# also needs to read this cookie to tell which session is the caller's own
# (`is_current` in api/routers/sessions.py) -- cookie path scoping is
# browser/client-enforced, so a narrower path here would silently make
# that comparison always fail outside of /auth/* routes. httpOnly+Secure+
# SameSite=lax are what actually protect this cookie; the path is not a
# meaningful second layer once more than one router needs it.
REFRESH_COOKIE_PATH = "/"


def set_refresh_cookie(response: Response, raw_refresh_token: str) -> None:
    """Sets the refresh-token cookie with all its security flags in one
    place, so every call site (register/login/refresh/OAuth callback)
    gets the exact same settings -- httpOnly (invisible to JS), Secure
    (HTTPS only, except in local dev via COOKIE_SECURE=False), SameSite=lax."""
    response.set_cookie(
        key=REFRESH_COOKIE_NAME,
        value=raw_refresh_token,
        max_age=settings.REFRESH_TOKEN_EXPIRE_DAYS * 24 * 3600,
        path=REFRESH_COOKIE_PATH,
        domain=settings.COOKIE_DOMAIN,
        secure=settings.COOKIE_SECURE,
        httponly=True,
        samesite="lax",
    )


def clear_refresh_cookie(response: Response) -> None:
    response.delete_cookie(
        key=REFRESH_COOKIE_NAME, path=REFRESH_COOKIE_PATH, domain=settings.COOKIE_DOMAIN
    )


async def enforce_concurrent_session_limit(db: AsyncSession, user_id: uuid.UUID) -> None:
    """
    Audit finding 14: caps how many sessions (devices/browsers) a single
    account may have active at once, at MAX_CONCURRENT_SESSIONS. Called
    from issue_session() below BEFORE the new session is created, so a
    user already AT the limit ends up back at the limit (oldest revoked,
    newest added) rather than one over it.

    Revokes the OLDEST active sessions to make room -- not rejecting the
    new login -- since the new login is always the one thing the real
    account owner is doing right now; an old session is the more likely
    one to be stale, forgotten, or (in the worst case) someone else's.
    Each revocation blacklists its access token too (revoke_session()),
    same as any other revocation, and the account is notified once per
    revoked session so a real owner would notice if this ever happened
    from an unexpected sign-in.
    """
    now = dt.datetime.now(dt.timezone.utc)
    active_sessions = (await db.scalars(
        select(Session)
        .where(Session.user_id == user_id, Session.revoked_at.is_(None), Session.expires_at > now)
        .order_by(Session.created_at.asc())
    )).all()

    to_revoke = len(active_sessions) - (settings.MAX_CONCURRENT_SESSIONS - 1)
    if to_revoke <= 0:
        return

    user = await db.get(User, user_id)
    for session in active_sessions[:to_revoke]:
        await revoke_session(db, session)
        await log_audit_action(
            db, user_id=user_id, action=AuditAction.CONCURRENT_SESSION_LIMIT, ip=None, user_agent=None,
            success=True, metadata={"revoked_session_id": str(session.id), "device_info": session.device_info},
        )
        if user is not None:
            try:
                send_concurrent_session_limit_reached_email(user.email, session.device_info)
            except (EnvironmentError, RuntimeError) as exc:
                logger.warning("failed to send session-limit notification to %s: %s", user.email, exc)


async def issue_session(
    db: AsyncSession, response: Response, request: Request, user_id: uuid.UUID, *, notify_new_device_email: str | None = None,
) -> TokenResponse:
    """
    Creates a new Session row (a fresh refresh token) and sets it as an
    httpOnly cookie, alongside a matching CSRF cookie (api/security/csrf.py);
    returns the access token for the JSON response body. The access
    token's own `jti` (api/security/jwt.py) is stored on the Session row
    it's paired with -- 1:1, since every refresh mints a brand new
    Session rather than reusing one -- so revoke_session() below can
    blacklist that exact access token when this session is revoked.

    notify_new_device_email: pass the user's email to get a "new sign-in"
    notification IF neither this device (User-Agent) NOR this network
    (IP address) has been seen together on a prior session for this user
    -- callers that represent an actual login (login(), refresh(), the
    OAuth callback, 2FA verify-login) pass it; register() does not,
    since a brand new account has no "usual" device yet to compare
    against (every login would look "new"). Checked before the new
    Session row is added, so this call's own session never counts as its
    own history.

    Requiring BOTH to match a single prior session (not User-Agent
    alone) is a deliberately stronger signal: a stolen refresh token
    replayed from a different network now still triggers the email even
    if the attacker also fakes a matching User-Agent string, since
    matching one signal alone is no longer enough to look "known." It's
    still not proof of identity -- both a User-Agent header and a source
    IP are attacker-influenceable in principle, and a legitimate user
    roaming between networks (home wifi to mobile data) will see more of
    these emails than before. That's an accepted trade -- a false
    positive here is an extra email; a false negative is a session
    hijack going unnoticed.
    """
    device_info = request.headers.get("user-agent")
    ip = client_ip(request)
    now = dt.datetime.now(dt.timezone.utc)

    await enforce_concurrent_session_limit(db, user_id)

    is_new_device = False
    if notify_new_device_email:
        prior_session_from_this_device_and_network = await db.scalar(
            select(Session.id).where(
                Session.user_id == user_id, Session.device_info == device_info, Session.ip_address == ip,
            ).limit(1)
        )
        is_new_device = prior_session_from_this_device_and_network is None

    access_token, access_token_jti = create_access_token(user_id)

    raw_refresh_token = generate_raw_token()
    session = Session(
        user_id=user_id,
        refresh_token_hash=hash_token(raw_refresh_token),
        access_token_jti=access_token_jti,
        device_info=device_info,
        ip_address=ip,
        expires_at=now + dt.timedelta(days=settings.REFRESH_TOKEN_EXPIRE_DAYS),
    )
    db.add(session)
    await db.flush()

    if notify_new_device_email and is_new_device:
        try:
            send_new_login_notification_email(notify_new_device_email, device_info, ip, now.isoformat())
        except (EnvironmentError, RuntimeError) as exc:
            logger.warning("failed to send new-login notification to %s: %s", notify_new_device_email, exc)

    set_refresh_cookie(response, raw_refresh_token)
    set_csrf_cookie(response, generate_csrf_token())
    return TokenResponse(
        access_token=access_token,
        expires_in=settings.ACCESS_TOKEN_EXPIRE_MINUTES * 60,
    )


async def get_active_session_by_raw_token(db: AsyncSession, raw_refresh_token: str) -> Session | None:
    """Looks up the Session row matching a raw refresh-token cookie value
    (by its hash -- the raw token itself is never stored, see
    api/models/session.py). Returns None for a token that doesn't match
    any row, or matches one that's expired or already revoked -- callers
    treat all three the same way (a rejected refresh)."""
    session = await db.scalar(select(Session).where(Session.refresh_token_hash == hash_token(raw_refresh_token)))
    if session is None or not session.is_active:
        return None
    return session


async def touch_session_and_check_idle_timeout(db: AsyncSession, access_token_jti: str) -> Session | None:
    """
    Audit findings 13/17: called on every authenticated request
    (api/dependencies.py's get_current_user_any_consent_status) for the
    Session paired 1:1 with the access token just used. Does BOTH of
    these in one round trip, not two, in the common case:

    - Refreshes last_seen_at to now -- previously written once at
      creation and never touched again, so it never actually reflected
      recent activity (this exact gap is what the audit caught).
    - Enforces SESSION_IDLE_TIMEOUT_MINUTES: the UPDATE's WHERE clause
      requires the row's PRE-update last_seen_at to already be within
      the idle window, so a session idle too long simply fails to match
      and last_seen_at is left untouched (not refreshed to now(), which
      would let a request arriving exactly at the timeout boundary
      silently reset the clock instead of expiring it).

    Returns None in the common case (touched successfully, or no
    matching row -- e.g. a pre-migration session with no
    access_token_jti at all, which this can't act on either way).
    Returns the Session if it WAS active but is now idle-timed-out, so
    the caller can revoke it (blacklisting its access token) and notify
    the account -- a mutation this function deliberately leaves to the
    caller rather than doing itself, so a read-only caller (there isn't
    one today, but this keeps the function honest about what "touch"
    means) is never surprised by it silently revoking anything.
    """
    now = dt.datetime.now(dt.timezone.utc)
    idle_cutoff = now - dt.timedelta(minutes=settings.SESSION_IDLE_TIMEOUT_MINUTES)

    result = await db.execute(
        update(Session)
        .where(
            Session.access_token_jti == access_token_jti,
            Session.revoked_at.is_(None),
            Session.expires_at > now,
            Session.last_seen_at > idle_cutoff,
        )
        .values(last_seen_at=now)
        .returning(Session.id)
        # Without this, the ORM also tries to re-evaluate this WHERE
        # clause in plain Python against any matching Session already
        # loaded in this AsyncSession's identity map, to keep it in
        # sync -- and SQLite (tests/conftest.py) round-trips a naive
        # datetime for last_seen_at while idle_cutoff above is
        # tz-aware, which raises "can't compare offset-naive and
        # offset-aware datetimes" the moment any test happens to have
        # this exact Session row already loaded. Not needed here: the
        # only two things done with the result are "did a row match"
        # and, on the caller's next request, a fresh SELECT -- nothing
        # depends on an in-memory ORM object being kept in sync inside
        # THIS request.
        .execution_options(synchronize_session=False)
    )
    if result.first() is not None:
        return None  # touched -- common case, nothing else to do

    # Either idle too long, or nothing matched for another reason
    # (already revoked/expired/no such session) -- the blacklist check
    # right before this call already ruled out "explicitly revoked," so
    # a still-active row found here specifically means idle timeout.
    session = await db.scalar(select(Session).where(Session.access_token_jti == access_token_jti))
    if session is not None and session.is_active:
        return session
    return None


async def revoke_session(db: AsyncSession, session: Session) -> None:
    """
    Marks one session dead (sets revoked_at) AND blacklists the access
    token minted alongside it (1.1.15, api/models/revoked_token.py), so
    revoking a session kills BOTH halves of that login immediately --
    not just the refresh token, which previously left any already-issued
    access token usable for up to its remaining ACCESS_TOKEN_EXPIRE_MINUTES.
    Used directly by logout, refresh-rotation (the OLD session, right
    before a new one is issued), and single-session revocation
    (DELETE /sessions/{id}); see revoke_all_sessions_for_user() below for
    the "every session this user has" case.

    access_token_jti can be None for a session row that predates this
    column (a real possibility during the migration window, never for a
    session created after it) -- nothing to blacklist for those, the
    refresh-token revocation above is still real and still happens.
    """
    session.revoked_at = dt.datetime.now(dt.timezone.utc)
    if session.access_token_jti:
        db.add(RevokedAccessToken(
            jti=session.access_token_jti,
            user_id=session.user_id,
            expires_at=session.created_at + dt.timedelta(minutes=settings.ACCESS_TOKEN_EXPIRE_MINUTES),
        ))
    await db.flush()


async def revoke_all_sessions_for_user(db: AsyncSession, user_id: uuid.UUID) -> None:
    """
    The bulk version of revoke_session() above, for every "something
    security-sensitive just happened, kill everything" call site:
    password reset, account deletion, consent withdrawal, 2FA disable,
    2FA lockout-recovery. Deliberately loops revoke_session() per row
    rather than a raw bulk DELETE -- a bulk DELETE would silently skip
    the access-token blacklist half of this, leaving every currently-
    outstanding access token for this user valid for up to its remaining
    ~15 minutes despite every session being gone. A user's active-session
    count is small (a handful of devices at most), so the extra
    round-trips this costs over a single DELETE are not a real concern.
    """
    sessions = (await db.scalars(
        select(Session).where(Session.user_id == user_id, Session.revoked_at.is_(None))
    )).all()
    for session in sessions:
        await revoke_session(db, session)
