"""
Core authentication endpoints: 1.1.1 register, 1.1.2 login/logout,
1.1.8 refresh. Every other auth router (password.py, verify.py, oauth.py,
two_factor.py, sessions.py) builds on the session/token machinery defined
here and in api/security/sessions.py.

How the token model works, in plain terms:
- A successful login/register/refresh returns a short-lived "access
  token" (a JWT, expires in ACCESS_TOKEN_EXPIRE_MINUTES) in the JSON
  response body. The frontend keeps this in memory and sends it as
  `Authorization: Bearer <token>` on every request that needs auth.
- At the same time, a long-lived "refresh token" is set as an httpOnly
  cookie (invisible to JavaScript, sent automatically by the browser).
  When the access token expires, the frontend calls POST /auth/refresh,
  which reads that cookie and issues a brand new access token + a brand
  new refresh token (the old one is immediately revoked -- see the
  comment on /refresh below for why).
"""

import datetime as dt
import logging

from fastapi import APIRouter, Cookie, Depends, HTTPException, Request, Response, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from api.config import settings
from api.dependencies import get_db
from api.models.audit_log import AuditAction
from api.models.user import User
from api.schemas.auth import LoginRequest, MessageResponse, MFARequiredResponse, RegisterRequest, TokenResponse
from api.security.audit_log import log_audit_action
from api.security.csrf import clear_csrf_cookie, verify_csrf
from api.security.hashing import hash_password, verify_password
from api.security.sessions import (
    clear_refresh_cookie,
    get_active_session_by_raw_token,
    issue_session,
    revoke_session,
)
from api.security.jwt import create_mfa_pending_token
from api.security.organizations import create_organization_with_owner
from api.security.webauthn import get_user_credentials
from api.security.password_history import record_password_change
from api.security.password_similarity import is_password_too_similar
from api.security.password_strength import is_password_known_breached
from api.security.adaptive_rate_limit import enforce_adaptive_rate_limit
from api.security.rate_limit import enforce_rate_limit
from api.services.email import send_rate_limit_alert_email
from api.services.security_alerts import check_and_alert_on_failed_login_spike
from api.services.verification import create_and_send_email_otp
from api.utils import client_ip

router = APIRouter(prefix="/auth", tags=["auth"])
logger = logging.getLogger(__name__)

# Reused for every login failure so the client never learns *which* part
# was wrong (unknown email vs. wrong password) -- see the comment inside
# login() for the reasoning.
_GENERIC_LOGIN_ERROR = HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Incorrect email or password")

_BREACHED_PASSWORD_ERROR = HTTPException(
    status_code=status.HTTP_400_BAD_REQUEST,
    detail="This password has appeared in a known data breach -- please choose a different one.",
)

# Audit finding 16.
_SIMILAR_PASSWORD_ERROR = HTTPException(
    status_code=status.HTTP_400_BAD_REQUEST,
    detail="This password is too similar to your email or name -- please choose a more distinct one.",
)

# 1.1-audit finding: bcrypt.checkpw costs ~250ms; `user is None or
# user.hashed_password is None or not verify_password(...)` short-circuits
# on the first two conditions, so an unknown email or an OAuth-only
# account returns in ~1ms while a known account with a wrong password
# takes ~250ms -- a textbook timing side-channel that lets an attacker
# enumerate registered emails by response time alone, despite every
# response body being identical. Hashed once at import time and reused
# below so a request with no real user to check against still pays the
# same bcrypt cost as one that does, closing the gap. The value itself
# is never a real account's password and is never compared against
# anything meaningful -- only its cost matters.
_DUMMY_PASSWORD_HASH_FOR_TIMING_SAFETY = hash_password("timing-safety-dummy-value-never-a-real-password")


@router.post("/register", response_model=TokenResponse, status_code=status.HTTP_201_CREATED)
async def register(payload: RegisterRequest, request: Request, response: Response, db: AsyncSession = Depends(get_db)):
    """
    Create a new account and log the user in immediately (the response
    already contains a working access token + refresh cookie -- there is
    no separate "please verify your email before you can do anything"
    gate). A verification code is emailed in the background regardless;
    see api/routers/verify.py for how the user later confirms it.

    Body: RegisterRequest (email, password, optional full_name/company,
    and accept_terms which Pydantic itself rejects if False -- see
    api/schemas/auth.py).
    """
    # Audit findings 29/30: geo-adaptive (country tier) and allowlist
    # (TRUSTED_IPS) aware -- see api/security/adaptive_rate_limit.py.
    # Behaviorally identical to a flat enforce_rate_limit() call until
    # those settings are actually configured.
    await enforce_adaptive_rate_limit(
        request, f"ratelimit:register:ip:{client_ip(request)}",
        settings.REGISTER_RATE_LIMIT_MAX_ATTEMPTS, settings.REGISTER_RATE_LIMIT_WINDOW_SECONDS,
    )

    existing = await db.scalar(select(User).where(User.email == payload.email))
    if existing is not None:
        # Deliberately vague: confirming "this email is already registered"
        # to an anonymous caller is a user-enumeration leak.
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Could not register with these details")

    if await is_password_known_breached(payload.password):
        raise _BREACHED_PASSWORD_ERROR

    if is_password_too_similar(payload.password, payload.email, payload.full_name):
        raise _SIMILAR_PASSWORD_ERROR

    hashed_password = hash_password(payload.password)
    user = User(
        email=payload.email,
        hashed_password=hashed_password,
        full_name=payload.full_name,
        company=payload.company,
        # 1.1.12 RGPD consent: recorded once, here, at the moment the user
        # actually agreed -- never edited afterwards, so it stays an
        # honest record of what was agreed to and when.
        consent_given_at=dt.datetime.now(dt.timezone.utc),
        terms_version=settings.TERMS_VERSION,
    )
    db.add(user)
    await db.flush()  # assigns user.id without committing yet -- needed below before the row is final
    # Audit finding 15: seeds the reuse-check history from a user's very
    # first password, not just from the first CHANGE -- otherwise
    # reusing this exact password again immediately after resetting it
    # would have nothing to catch it against.
    await record_password_change(db, user.id, hashed_password)

    # Etape 1.2.2 -- every new account gets a default organization, with
    # itself as Owner. Part of the SAME transaction as the user row
    # itself (no commit in between): if this fails, the whole
    # registration rolls back rather than leaving a real account with no
    # organization at all. OAuth/SSO sign-up (api/routers/oauth.py,
    # api/routers/enterprise_sso.py) do not yet get this -- out of scope
    # for this step, a disclosed gap, not an oversight.
    await create_organization_with_owner(
        db, name=f"Organisation de {user.email}", owner_user_id=user.id,
        ip=client_ip(request), user_agent=request.headers.get("user-agent"),
    )

    await create_and_send_email_otp(db, user)  # 1.1.4 -- fire-and-forget-ish: logs a warning and continues on email failure, never blocks registration
    # No notify_new_device_email here: this is the account's first-ever
    # session, so there's no "usual device" yet to compare against --
    # every registration would otherwise look like a suspicious new login.
    tokens = await issue_session(db, response, request, user.id)
    await log_audit_action(
        db, user_id=user.id, action=AuditAction.REGISTER, ip=client_ip(request),
        user_agent=request.headers.get("user-agent"), success=True,
    )
    await db.commit()
    return tokens


@router.post("/login", response_model=None)
async def login(payload: LoginRequest, request: Request, response: Response, db: AsyncSession = Depends(get_db)) -> TokenResponse | MFARequiredResponse:
    """
    Password login. Returns one of two shapes depending on whether the
    account has 2FA enabled:
    - TokenResponse: normal case, access token + refresh cookie, done.
    - MFARequiredResponse: the password was correct but the account has
      TOTP enabled (see api/routers/two_factor.py) -- the frontend must
      then call POST /auth/2fa/verify-login with the returned mfa_token
      and a 6-digit code before it gets real tokens. This second call is
      the only place tokens are actually issued for a 2FA account.

    Rate-limited along two independent dimensions (whichever is hit
    first blocks the request): by IP, so one attacker can't brute-force
    many different accounts from one machine, and by the target email,
    so a distributed attack (many IPs, one victim account) is still
    caught even though no single IP looks suspicious on its own. Hitting
    the email-scoped limit also emails the account owner (if the email
    belongs to a real account) that repeated attempts were blocked --
    the one mitigation for the fact that an *attacker* can trigger this
    same limit to lock the real owner out for a while too; at least they
    find out it's happening.
    """
    # Audit findings 29/30 -- see the matching comment in register() above.
    await enforce_adaptive_rate_limit(
        request, f"ratelimit:login:ip:{client_ip(request)}",
        settings.LOGIN_RATE_LIMIT_MAX_ATTEMPTS, settings.LOGIN_RATE_LIMIT_WINDOW_SECONDS,
    )

    user = await db.scalar(select(User).where(User.email == payload.email))

    try:
        await enforce_rate_limit(
            f"ratelimit:login:email:{payload.email}",
            settings.LOGIN_RATE_LIMIT_MAX_ATTEMPTS, settings.LOGIN_RATE_LIMIT_WINDOW_SECONDS,
        )
    except HTTPException:
        if user is not None:
            try:
                send_rate_limit_alert_email(user.email, "sign-in")
            except (EnvironmentError, RuntimeError) as exc:
                logger.warning("failed to send rate-limit alert to %s: %s", user.email, exc)
        raise

    # Every one of these three distinct failure reasons -- unknown email,
    # OAuth-only account with no password set, wrong password -- raises
    # the exact same generic error. Returning a different message for
    # "that email doesn't exist" vs "wrong password" would let an
    # attacker enumerate which emails are registered one guess at a time.
    #
    # verify_password is called UNCONDITIONALLY, even when there's no real
    # hash to check against (falling back to the dummy one above) -- not
    # short-circuited by `user is None or ...`. bcrypt's ~250ms cost is
    # otherwise only paid on the "user exists" branch, which is a timing
    # side-channel that defeats the identical-response-body protection
    # above just as effectively as a different error message would.
    real_hash = user.hashed_password if (user is not None and user.hashed_password is not None) else _DUMMY_PASSWORD_HASH_FOR_TIMING_SAFETY
    password_matches = verify_password(payload.password, real_hash)
    ip = client_ip(request)
    user_agent = request.headers.get("user-agent")

    if user is None or user.hashed_password is None or not password_matches:
        await log_audit_action(
            db, user_id=(user.id if user is not None else None), action=AuditAction.LOGIN_FAILED, ip=ip,
            user_agent=user_agent, success=False, failure_reason="invalid_credentials", metadata={"email": payload.email},
        )
        await db.commit()
        await check_and_alert_on_failed_login_spike(db, ip, payload.email)
        raise _GENERIC_LOGIN_ERROR
    if not user.is_active or user.is_deleted:
        await log_audit_action(
            db, user_id=user.id, action=AuditAction.LOGIN_FAILED, ip=ip, user_agent=user_agent,
            success=False, failure_reason="account_inactive", metadata={"email": payload.email},
        )
        await db.commit()
        raise _GENERIC_LOGIN_ERROR

    # Audit finding 26: WebAuthn is an ADDITIONAL available second factor,
    # never a replacement for TOTP -- an account can have either, both,
    # or neither. available_methods tells the frontend which ceremony(s)
    # this specific account can actually complete; both ultimately
    # consume the same mfa_token (see MFARequiredResponse's docstring).
    webauthn_credentials = await get_user_credentials(db, user.id)
    if user.totp_enabled or webauthn_credentials:
        available_methods = []
        if user.totp_enabled:
            available_methods.append("totp")
        if webauthn_credentials:
            available_methods.append("webauthn")
        return MFARequiredResponse(mfa_token=create_mfa_pending_token(user.id), available_methods=available_methods)

    tokens = await issue_session(db, response, request, user.id, notify_new_device_email=user.email, remember_me=payload.remember_me)
    await log_audit_action(db, user_id=user.id, action=AuditAction.LOGIN_SUCCESS, ip=ip, user_agent=user_agent, success=True)
    await db.commit()
    return tokens


@router.post("/refresh", response_model=TokenResponse)
async def refresh(
    request: Request,
    response: Response,
    refresh_token: str | None = Cookie(default=None),
    db: AsyncSession = Depends(get_db),
    _csrf: None = Depends(verify_csrf),
):
    """
    Exchange the httpOnly refresh cookie for a brand new access token
    (and a brand new refresh cookie -- rotation, see below). The frontend
    calls this whenever an access token expires (every
    ACCESS_TOKEN_EXPIRE_MINUTES) rather than asking the user to log in
    again every 15 minutes.

    CSRF-protected (api/security/csrf.py): this is one of only two
    endpoints (the other is /auth/logout) that authenticate purely off a
    cookie, with no Authorization header to prove the caller is who they
    claim -- exactly the shape a cross-site forged request could
    otherwise ride on.
    """
    unauthorized = HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid or expired refresh token, please log in again")
    if not refresh_token:
        raise unauthorized

    session = await get_active_session_by_raw_token(db, refresh_token)
    if session is None:
        clear_refresh_cookie(response)
        clear_csrf_cookie(response)
        raise unauthorized

    user = await db.get(User, session.user_id)
    if user is None or not user.is_active or user.is_deleted:
        clear_refresh_cookie(response)
        clear_csrf_cookie(response)
        raise unauthorized

    # Rotation (1.1.8): the consumed refresh token is revoked, not reused --
    # a stolen-then-replayed old token fails the is_active check on its
    # second use instead of silently working forever.
    await revoke_session(db, session)
    # notify_new_device_email here too: a normal refresh from the same
    # browser/app matches its own prior session's device_info and stays
    # silent, but a refresh token used from a genuinely different device
    # (e.g. a stolen cookie replayed elsewhere) does NOT match any prior
    # device for this user and triggers the same "new sign-in" email as
    # a fresh login would.
    tokens = await issue_session(db, response, request, user.id, notify_new_device_email=user.email)
    await db.commit()
    return tokens


@router.post("/logout", response_model=MessageResponse)
async def logout(
    request: Request, response: Response, refresh_token: str | None = Cookie(default=None), db: AsyncSession = Depends(get_db),
    _csrf: None = Depends(verify_csrf),
):
    """
    Ends the current session: revokes the refresh token server-side (so
    it can never be used again, even if someone captured a copy of the
    cookie before this call), blacklists the paired access token too
    (revoke_session() -- api/security/sessions.py, 1.1.15), and clears
    both cookies in the browser. Tolerant of being called with no cookie
    at all -- logging out twice, or logging out after the session
    already expired, is not an error.

    CSRF-protected, see /auth/refresh's docstring above for why.
    """
    if refresh_token:
        session = await get_active_session_by_raw_token(db, refresh_token)
        if session is not None:
            await revoke_session(db, session)
            await log_audit_action(
                db, user_id=session.user_id, action=AuditAction.LOGOUT, ip=client_ip(request),
                user_agent=request.headers.get("user-agent"), success=True,
            )
            await db.commit()
    clear_refresh_cookie(response)
    clear_csrf_cookie(response)
    return MessageResponse(message="Logged out")
