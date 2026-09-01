"""
1.1.7 -- TOTP setup/enable/disable, plus the login-time verification step
that auth.py's /auth/login hands off to when totp_enabled is True.

/setup only stores a *pending* secret -- totp_enabled stays False until
/enable proves the user actually scanned the QR code and their
authenticator app produces matching codes. Skipping that proof would let a
setup call that's never followed through lock nothing, but also means a
user could think 2FA is on when it isn't; requiring /enable's confirmation
avoids that false sense of security.

4.3: the account-security endpoints here (/setup, /enable, /disable,
/recovery-codes/regenerate, /recovery-codes/status) use
get_current_user_any_consent_status rather than get_current_user, so they
stay reachable even for an account that hasn't accepted updated terms
yet -- same exemption reasoning as api/routers/sessions.py. Each of these
already requires either no prior 2FA state or a valid current TOTP code
(see each endpoint's own docstring), so they're a basic account-security
action, not "ordinary use of the service" -- a user locked out of the app
by a stale-terms 403 must still be able to turn 2FA on/off or rotate
their recovery codes, the same way they must still be able to see or
revoke their own sessions.
"""

import datetime as dt
import logging
import uuid

from fastapi import APIRouter, Depends, HTTPException, Request, Response, status
from jwt import ExpiredSignatureError, InvalidTokenError
from sqlalchemy import delete, func, select, update
from sqlalchemy.ext.asyncio import AsyncSession

from api.config import settings
from api.dependencies import get_current_user_any_consent_status, get_db
from api.models.audit_log import AuditAction
from api.models.lockout_recovery_token import TwoFactorLockoutRecoveryToken
from api.models.recovery_code import TwoFactorRecoveryCode
from api.models.user import User
from api.schemas.auth import (
    MessageResponse,
    TokenResponse,
    TwoFactorCodeRequest,
    TwoFactorLockoutRecoveryConfirmRequest,
    TwoFactorLockoutRecoveryRequest,
    TwoFactorRecoveryCodeLoginRequest,
    TwoFactorRecoveryCodesResponse,
    TwoFactorRecoveryCodesStatusResponse,
    TwoFactorSetupResponse,
    TwoFactorVerifyLoginRequest,
)
from api.security.audit_log import log_audit_action
from api.security.hashing import hash_token, verify_password
from api.security.jwt import InvalidTokenPurposeError, TokenPurpose, decode_token
from api.security.rate_limit import enforce_rate_limit
from api.security.recovery_codes import (
    RECOVERY_CODE_COUNT,
    build_recovery_codes_file,
    generate_recovery_code,
    normalize_recovery_code,
)
from api.security.sessions import issue_session, revoke_all_sessions_for_user
from api.security.totp import generate_totp_secret, totp_provisioning_qr_data_uri, verify_totp_code
from api.services.email import (
    send_recovery_code_used_email,
    send_recovery_codes_regenerated_email,
    send_two_factor_disabled_email,
    send_two_factor_enabled_email,
    send_two_factor_lockout_recovery_completed_email,
)
from api.services.two_factor_lockout_recovery import create_and_send_two_factor_lockout_recovery
from api.utils import as_aware_utc, client_ip

router = APIRouter(prefix="/auth/2fa", tags=["auth"])
logger = logging.getLogger(__name__)

_GENERIC_LOCKOUT_RECOVERY_MESSAGE = (
    "If that email and password match an account with two-factor authentication enabled, "
    "a recovery link has been sent."
)


async def _replace_recovery_codes(db: AsyncSession, user_id: uuid.UUID) -> list[str]:
    """Deletes every existing recovery code row for this user and inserts
    a fresh batch of RECOVERY_CODE_COUNT, returning the plaintext codes
    for the caller to show exactly once. Deleting first (rather than just
    adding more) means an old batch can never be combined with a new one
    to end up with more valid codes floating around than intended, and
    guarantees a disable/re-enable or a regenerate call fully invalidates
    whatever came before it."""
    await db.execute(delete(TwoFactorRecoveryCode).where(TwoFactorRecoveryCode.user_id == user_id))
    plain_codes = [generate_recovery_code() for _ in range(RECOVERY_CODE_COUNT)]
    for code in plain_codes:
        db.add(TwoFactorRecoveryCode(user_id=user_id, code_hash=hash_token(normalize_recovery_code(code))))
    await db.flush()
    return plain_codes


async def _cancel_pending_lockout_recovery(db: AsyncSession, user_id: uuid.UUID) -> None:
    """A successful TOTP or recovery-code login is proof the account
    owner still controls 2FA -- any /2fa/lockout-recovery/request still
    pending for this account is exactly what an attacker who only has
    the password would be relying on instead, so it's invalidated here
    rather than left to silently mature over its delay window. Called
    from every path that proves 2FA is still under the real owner's
    control: /verify-login, /verify-recovery-code, and /disable."""
    await db.execute(
        delete(TwoFactorLockoutRecoveryToken).where(
            TwoFactorLockoutRecoveryToken.user_id == user_id, TwoFactorLockoutRecoveryToken.used_at.is_(None)
        )
    )


@router.post("/setup", response_model=TwoFactorSetupResponse)
async def setup_two_factor(current_user: User = Depends(get_current_user_any_consent_status), db: AsyncSession = Depends(get_db)):
    """
    Step 1 of turning 2FA on: generates a new TOTP secret and returns it
    two ways -- as plain text (for apps that want manual entry) and as a
    QR code (a base64 PNG data: URI the frontend can drop straight into
    an <img> tag) encoding the same secret in the standard otpauth://
    format any authenticator app understands. The secret is saved on the
    user row immediately, but totp_enabled stays False -- see this
    module's docstring for why /enable is a required second step.
    """
    if current_user.totp_enabled:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Two-factor authentication is already enabled")

    secret = generate_totp_secret()
    current_user.totp_secret = secret
    await db.commit()

    return TwoFactorSetupResponse(
        secret=secret,
        qr_code_data_uri=totp_provisioning_qr_data_uri(secret, current_user.email),
    )


@router.post("/enable", response_model=TwoFactorRecoveryCodesResponse)
async def enable_two_factor(payload: TwoFactorCodeRequest, request: Request, current_user: User = Depends(get_current_user_any_consent_status), db: AsyncSession = Depends(get_db)):
    """
    Step 2: proves the user actually scanned the QR code from /setup by
    submitting the current 6-digit code their authenticator app is now
    showing. Only once that code checks out does totp_enabled flip to
    True -- from this point on, password login alone is not enough (see
    auth.py's login() and /verify-login below).

    Also mints a fresh batch of recovery codes (see
    api/security/recovery_codes.py) and returns them in plaintext -- the
    only response that will ever contain them. A lost/reset authenticator
    device would otherwise permanently lock the user out, since nothing
    else on this account can produce a valid TOTP code.

    Rate-limited by user id: this endpoint only needs a valid access
    token, not the TOTP secret itself, so without a limit a stolen token
    alone would let an attacker brute-force the 6-digit code the same
    way /verify-login guards against.

    Always emails the account that 2FA was just turned on. This is not
    just a courtesy: /setup returns the secret in plaintext (as a
    otpauth:// QR code) to whoever holds a valid access token, and this
    endpoint only needs THAT plus a code computed from it -- an attacker
    with a stolen access token could scan that QR code into their OWN
    authenticator and enable 2FA under a secret only they control,
    silently locking the real owner out of their own account the next
    time they try to log in. The email is the one signal that would
    catch that in time, since nothing else about the request looks
    abnormal (a valid token calling an endpoint it's allowed to call).
    """
    await enforce_rate_limit(
        f"ratelimit:2fa-code:user:{current_user.id}",
        settings.TWO_FA_VERIFY_RATE_LIMIT_MAX_ATTEMPTS, settings.TWO_FA_VERIFY_RATE_LIMIT_WINDOW_SECONDS,
    )
    if not current_user.totp_secret:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Call /auth/2fa/setup first")
    if not verify_totp_code(current_user.totp_secret, payload.code):
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Invalid code")

    current_user.totp_enabled = True
    plain_codes = await _replace_recovery_codes(db, current_user.id)
    await log_audit_action(
        db, user_id=current_user.id, action=AuditAction.TWO_FA_ENABLED, ip=client_ip(request),
        user_agent=request.headers.get("user-agent"), success=True,
    )
    await db.commit()

    try:
        send_two_factor_enabled_email(current_user.email)
    except (EnvironmentError, RuntimeError) as exc:
        logger.warning("failed to send 2FA-enabled notification to %s: %s", current_user.email, exc)

    return TwoFactorRecoveryCodesResponse(recovery_codes=plain_codes, recovery_codes_file=build_recovery_codes_file(plain_codes))


@router.post("/disable", response_model=MessageResponse)
async def disable_two_factor(payload: TwoFactorCodeRequest, request: Request, current_user: User = Depends(get_current_user_any_consent_status), db: AsyncSession = Depends(get_db)):
    """
    Turns 2FA back off -- still requires a valid current code, not just
    the access token, so someone who stole a logged-in session/laptop
    can't disable the extra protection without also having the physical
    authenticator device.

    Also deletes every remaining recovery code: with 2FA off, they have
    no purpose, and leaving them valid would let a leaked old code be
    combined with a future re-enable to reconstruct backdoor access that
    the user never actually re-issued.

    Rate-limited by user id, same reasoning as /enable above: a stolen
    access token alone must not be enough to brute-force this account's
    TOTP code and turn 2FA off.

    Always emails the account that 2FA was turned off: this already
    requires a valid current TOTP code, a much stronger bar than /enable's
    (see that endpoint's docstring), but a stolen unlocked device with
    the authenticator app already open -- or a session compromised right
    after setup -- could still pass it. The notification is what lets
    the real owner notice before someone else logs in with just the
    password.
    """
    await enforce_rate_limit(
        f"ratelimit:2fa-code:user:{current_user.id}",
        settings.TWO_FA_VERIFY_RATE_LIMIT_MAX_ATTEMPTS, settings.TWO_FA_VERIFY_RATE_LIMIT_WINDOW_SECONDS,
    )
    if not current_user.totp_enabled or not current_user.totp_secret:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Two-factor authentication is not enabled")
    if not verify_totp_code(current_user.totp_secret, payload.code):
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Invalid code")

    current_user.totp_enabled = False
    current_user.totp_secret = None
    await db.execute(delete(TwoFactorRecoveryCode).where(TwoFactorRecoveryCode.user_id == current_user.id))
    await _cancel_pending_lockout_recovery(db, current_user.id)
    await log_audit_action(
        db, user_id=current_user.id, action=AuditAction.TWO_FA_DISABLED, ip=client_ip(request),
        user_agent=request.headers.get("user-agent"), success=True,
    )
    await db.commit()

    try:
        send_two_factor_disabled_email(current_user.email)
    except (EnvironmentError, RuntimeError) as exc:
        logger.warning("failed to send 2FA-disabled notification to %s: %s", current_user.email, exc)

    return MessageResponse(message="Two-factor authentication disabled")


@router.post("/recovery-codes/regenerate", response_model=TwoFactorRecoveryCodesResponse)
async def regenerate_recovery_codes(payload: TwoFactorCodeRequest, current_user: User = Depends(get_current_user_any_consent_status), db: AsyncSession = Depends(get_db)):
    """
    Invalidates every unused code from the previous batch and issues a
    fresh set of RECOVERY_CODE_COUNT -- for a user who has used some/all
    of their original codes, or suspects one was seen by someone else.

    Requires a valid current TOTP code, not just a valid access token,
    for the same reason /disable does: a stolen access token alone must
    not be enough to mint a fresh, persistent bypass for the account.
    Rate-limited by user id for that same reason.

    Always emails the account: regenerating silently invalidates every
    recovery code the real owner may have saved -- worth flagging for
    the same reason /disable is, even though it already requires a
    valid current TOTP code to reach.
    """
    await enforce_rate_limit(
        f"ratelimit:2fa-code:user:{current_user.id}",
        settings.TWO_FA_VERIFY_RATE_LIMIT_MAX_ATTEMPTS, settings.TWO_FA_VERIFY_RATE_LIMIT_WINDOW_SECONDS,
    )
    if not current_user.totp_enabled or not current_user.totp_secret:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Two-factor authentication is not enabled")
    if not verify_totp_code(current_user.totp_secret, payload.code):
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Invalid code")

    plain_codes = await _replace_recovery_codes(db, current_user.id)
    await db.commit()

    try:
        send_recovery_codes_regenerated_email(current_user.email)
    except (EnvironmentError, RuntimeError) as exc:
        logger.warning("failed to send recovery-codes-regenerated notification to %s: %s", current_user.email, exc)

    return TwoFactorRecoveryCodesResponse(recovery_codes=plain_codes, recovery_codes_file=build_recovery_codes_file(plain_codes))


@router.get("/recovery-codes/status", response_model=TwoFactorRecoveryCodesStatusResponse)
async def recovery_codes_status(current_user: User = Depends(get_current_user_any_consent_status), db: AsyncSession = Depends(get_db)):
    """
    Lets the frontend show "3 of 10 recovery codes remaining" so a user
    finds out they're running low BEFORE they're locked out of both
    their authenticator and every code, rather than discovering it only
    when /verify-recovery-code starts failing. Counts only -- never
    returns the codes themselves, which is impossible anyway since only
    their hashes are ever stored (see TwoFactorRecoveryCode).

    total is 0 (not RECOVERY_CODE_COUNT) when 2FA isn't enabled at all --
    "0 of 10 remaining" would misleadingly imply a recovery system that
    doesn't currently exist for this account rather than one that's just
    never been set up.
    """
    if not current_user.totp_enabled:
        return TwoFactorRecoveryCodesStatusResponse(total=0, remaining=0)

    remaining = await db.scalar(
        select(func.count()).select_from(TwoFactorRecoveryCode).where(
            TwoFactorRecoveryCode.user_id == current_user.id, TwoFactorRecoveryCode.used_at.is_(None)
        )
    )
    return TwoFactorRecoveryCodesStatusResponse(total=RECOVERY_CODE_COUNT, remaining=remaining or 0)


@router.post("/verify-login", response_model=TokenResponse)
async def verify_two_factor_login(payload: TwoFactorVerifyLoginRequest, request: Request, response: Response, db: AsyncSession = Depends(get_db)):
    """
    The second half of logging in to a 2FA-enabled account: auth.py's
    /auth/login already checked the password and, seeing totp_enabled,
    handed back a short-lived mfa_token instead of real tokens. This
    endpoint takes that mfa_token plus the current 6-digit code and, if
    both check out, issues the real access token + refresh cookie -- the
    password is never asked for again at this step, the mfa_token itself
    (see api/security/jwt.py's TokenPurpose.MFA_PENDING) is what proves
    the password was already correct a moment ago.

    Rate-limited by the mfa_token itself (hashed -- same reasoning as
    never storing a raw token elsewhere in this codebase), not by IP:
    this caps how many codes can be guessed against this ONE pending
    login "session" before it has to be restarted from /auth/login,
    which is what actually stops a 6-digit TOTP code from being
    brute-forced (1,000,000 possibilities is nothing without a limit).
    """
    await enforce_rate_limit(
        f"ratelimit:2fa-verify:token:{hash_token(payload.mfa_token)}",
        settings.TWO_FA_VERIFY_RATE_LIMIT_MAX_ATTEMPTS, settings.TWO_FA_VERIFY_RATE_LIMIT_WINDOW_SECONDS,
    )

    unauthorized = HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid or expired MFA session, please log in again")
    try:
        user_id = decode_token(payload.mfa_token, TokenPurpose.MFA_PENDING).user_id
    except (ExpiredSignatureError, InvalidTokenError, InvalidTokenPurposeError):
        raise unauthorized

    user = await db.get(User, user_id)
    if user is None or not user.is_active or user.is_deleted or not user.totp_enabled or not user.totp_secret:
        raise unauthorized
    if not verify_totp_code(user.totp_secret, payload.code):
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid code")

    # Proof the real owner still controls 2FA -- cancel any pending
    # /lockout-recovery/request an attacker (who'd only have the
    # password) might be relying on instead. See its docstring below.
    await _cancel_pending_lockout_recovery(db, user.id)

    tokens = await issue_session(db, response, request, user.id, notify_new_device_email=user.email)
    await db.commit()
    return tokens


@router.post("/verify-recovery-code", response_model=TokenResponse)
async def verify_two_factor_recovery_code(payload: TwoFactorRecoveryCodeLoginRequest, request: Request, response: Response, db: AsyncSession = Depends(get_db)):
    """
    Fallback for /verify-login when the user has lost access to their
    authenticator app (phone lost, reset, or the app uninstalled) --
    consumes one of the single-use codes from /enable or a later
    /recovery-codes/regenerate instead of a 6-digit TOTP code. Same
    mfa_token handoff from /auth/login as /verify-login.

    Rate-limited the same way as /verify-login, but under its own Redis
    key: guessing recovery codes and guessing TOTP codes are independent
    attacks and shouldn't share one counter (an attacker exhausting the
    TOTP attempts shouldn't also burn the user's recovery-code attempts,
    and vice versa).
    """
    await enforce_rate_limit(
        f"ratelimit:2fa-recovery:token:{hash_token(payload.mfa_token)}",
        settings.TWO_FA_VERIFY_RATE_LIMIT_MAX_ATTEMPTS, settings.TWO_FA_VERIFY_RATE_LIMIT_WINDOW_SECONDS,
    )

    unauthorized = HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid or expired MFA session, please log in again")
    try:
        user_id = decode_token(payload.mfa_token, TokenPurpose.MFA_PENDING).user_id
    except (ExpiredSignatureError, InvalidTokenError, InvalidTokenPurposeError):
        raise unauthorized

    user = await db.get(User, user_id)
    if user is None or not user.is_active or user.is_deleted or not user.totp_enabled:
        raise unauthorized

    # A single conditional UPDATE, not a SELECT followed by a write: the
    # WHERE clause (including used_at IS NULL) is evaluated atomically by
    # the database as part of the UPDATE itself, so two concurrent
    # requests replaying the same still-valid code can't both succeed --
    # whichever commits first flips used_at, and the second UPDATE's own
    # WHERE no longer matches that row, matching zero rows instead of
    # racing a Python-level check-then-write against another request.
    code_hash = hash_token(normalize_recovery_code(payload.recovery_code))
    result = await db.execute(
        update(TwoFactorRecoveryCode)
        .where(
            TwoFactorRecoveryCode.user_id == user.id,
            TwoFactorRecoveryCode.code_hash == code_hash,
            TwoFactorRecoveryCode.used_at.is_(None),
        )
        .values(used_at=dt.datetime.now(dt.timezone.utc))
        .returning(TwoFactorRecoveryCode.id)
    )
    if result.scalar_one_or_none() is None:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid or already-used recovery code")

    try:
        send_recovery_code_used_email(user.email)
    except (EnvironmentError, RuntimeError) as exc:
        logger.warning("failed to send recovery-code-used alert to %s: %s", user.email, exc)

    await _cancel_pending_lockout_recovery(db, user.id)

    tokens = await issue_session(db, response, request, user.id, notify_new_device_email=user.email)
    await db.commit()
    return tokens


@router.post("/lockout-recovery/request", response_model=MessageResponse)
async def request_two_factor_lockout_recovery(payload: TwoFactorLockoutRecoveryRequest, request: Request, db: AsyncSession = Depends(get_db)):
    """
    True last resort: a user who has lost BOTH their authenticator
    device AND all 10 recovery codes can satisfy neither /verify-login
    nor /verify-recovery-code, and would otherwise be permanently locked
    out. Takes the account password (not just the email) as a stronger
    claim than a bare "I can read this mailbox" -- and even then does
    NOT disable 2FA here; see /confirm below for the mandatory delay.

    Rate-limited by IP and by email, same reasoning and same thresholds
    as /auth/login: this endpoint checks a password guess, so it needs
    the same brute-force protection login itself has.

    Always returns the same generic message, whether or not the email
    exists, has a password, or has 2FA enabled -- anti-enumeration, same
    as /auth/password/forgot.
    """
    await enforce_rate_limit(
        f"ratelimit:2fa-lockout:ip:{client_ip(request)}",
        settings.LOGIN_RATE_LIMIT_MAX_ATTEMPTS, settings.LOGIN_RATE_LIMIT_WINDOW_SECONDS,
    )
    await enforce_rate_limit(
        f"ratelimit:2fa-lockout:email:{payload.email}",
        settings.LOGIN_RATE_LIMIT_MAX_ATTEMPTS, settings.LOGIN_RATE_LIMIT_WINDOW_SECONDS,
    )

    user = await db.scalar(select(User).where(User.email == payload.email))
    if (
        user is not None
        and user.hashed_password is not None
        and verify_password(payload.password, user.hashed_password)
        and user.is_active
        and not user.is_deleted
        and user.totp_enabled
    ):
        await create_and_send_two_factor_lockout_recovery(db, user)
        await db.commit()
    return MessageResponse(message=_GENERIC_LOCKOUT_RECOVERY_MESSAGE)


@router.post("/lockout-recovery/confirm", response_model=MessageResponse)
async def confirm_two_factor_lockout_recovery(payload: TwoFactorLockoutRecoveryConfirmRequest, db: AsyncSession = Depends(get_db)):
    """
    Step 2, only reachable once TWO_FA_LOCKOUT_RECOVERY_DELAY_HOURS have
    passed since /request -- the delay is what a phisher or device thief
    can't wait out unnoticed, while the real owner would see the "2FA
    removal requested" email and log in normally (which cancels every
    pending token for this account, see _cancel_pending_lockout_recovery
    and its call sites) to stop it before it ever becomes eligible.

    On success, disables 2FA entirely (not just this one login) and logs
    every device out -- this is as security-sensitive as a password
    reset, and treated the same way.
    """
    invalid = HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Invalid, expired, or not-yet-eligible recovery link")

    row = await db.scalar(select(TwoFactorLockoutRecoveryToken).where(TwoFactorLockoutRecoveryToken.token_hash == hash_token(payload.token)))
    now = dt.datetime.now(dt.timezone.utc)
    if row is None or row.used_at is not None or as_aware_utc(row.expires_at) < now:
        raise invalid
    if as_aware_utc(row.created_at) + dt.timedelta(hours=settings.TWO_FA_LOCKOUT_RECOVERY_DELAY_HOURS) > now:
        raise invalid

    user = await db.get(User, row.user_id)
    if user is None or not user.totp_enabled:
        raise invalid

    user.totp_enabled = False
    user.totp_secret = None
    await db.execute(delete(TwoFactorRecoveryCode).where(TwoFactorRecoveryCode.user_id == user.id))
    # 1.1.15: blacklists each session's access token too, not just its
    # refresh token -- a stolen access token must not outlive this.
    await revoke_all_sessions_for_user(db, user.id)
    row.used_at = now
    await db.commit()

    try:
        send_two_factor_lockout_recovery_completed_email(user.email)
    except (EnvironmentError, RuntimeError) as exc:
        logger.warning("failed to send lockout-recovery completion email to %s: %s", user.email, exc)

    return MessageResponse(message="Two-factor authentication has been disabled. Please log in with your password.")
