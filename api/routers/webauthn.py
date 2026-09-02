"""
Audit finding 26 -- WebAuthn/FIDO2 as a second factor, alongside (never
instead of) TOTP (api/routers/two_factor.py). Mirrors that router's
shape closely: setup/verify to register, an mfa_token-bridged
verify-login to authenticate -- see api/security/webauthn.py's module
docstring for the underlying ceremony/challenge-storage details.
"""

import datetime as dt
import logging
import uuid

from fastapi import APIRouter, Depends, HTTPException, Request, Response, status
from jwt import ExpiredSignatureError, InvalidTokenError
from sqlalchemy import delete
from sqlalchemy.ext.asyncio import AsyncSession
from webauthn.helpers import base64url_to_bytes
from webauthn.helpers.exceptions import WebAuthnException

from api.config import settings
from api.dependencies import get_current_user_any_consent_status, get_db
from api.models.audit_log import AuditAction
from api.models.lockout_recovery_token import TwoFactorLockoutRecoveryToken
from api.models.user import User
from api.models.webauthn_credential import WebAuthnCredential
from api.schemas.auth import TokenResponse
from api.schemas.webauthn import (
    WebAuthnAuthenticationOptionsRequest,
    WebAuthnAuthenticationVerifyRequest,
    WebAuthnCredentialEntry,
    WebAuthnCredentialListResponse,
    WebAuthnRegistrationVerifyRequest,
)
from api.security.audit_log import log_audit_action
from api.security.hashing import hash_token
from api.security.jwt import InvalidTokenPurposeError, TokenPurpose, decode_token
from api.security.rate_limit import enforce_rate_limit
from api.security.sessions import issue_session
from api.security.webauthn import (
    build_authentication_options,
    build_registration_options,
    get_user_credentials,
    verify_authentication,
    verify_registration,
)
from api.services.email import send_webauthn_credential_added_email, send_webauthn_credential_removed_email
from api.utils import client_ip

router = APIRouter(prefix="/auth/webauthn", tags=["auth"])
logger = logging.getLogger(__name__)

_TOO_MANY_CREDENTIALS = HTTPException(
    status_code=status.HTTP_400_BAD_REQUEST,
    detail=f"You already have the maximum of {settings.WEBAUTHN_MAX_CREDENTIALS_PER_USER} security keys registered",
)


@router.post("/register/options")
async def webauthn_registration_options(
    current_user: User = Depends(get_current_user_any_consent_status), db: AsyncSession = Depends(get_db),
):
    """
    Step 1 of registering a new physical key/authenticator -- returns the
    options blob `navigator.credentials.create()` expects, verbatim (see
    api/security/webauthn.py's build_registration_options). Checked
    against WEBAUTHN_MAX_CREDENTIALS_PER_USER BEFORE generating a
    challenge, so hitting the limit doesn't burn a Redis round trip (or a
    challenge slot) for nothing.
    """
    existing = await get_user_credentials(db, current_user.id)
    if len(existing) >= settings.WEBAUTHN_MAX_CREDENTIALS_PER_USER:
        raise _TOO_MANY_CREDENTIALS

    options_json = await build_registration_options(current_user.id, current_user.email, existing)
    return Response(content=options_json, media_type="application/json")


@router.post("/register/verify", response_model=WebAuthnCredentialEntry)
async def webauthn_registration_verify(
    payload: WebAuthnRegistrationVerifyRequest, request: Request,
    current_user: User = Depends(get_current_user_any_consent_status), db: AsyncSession = Depends(get_db),
):
    """
    Step 2: verifies the browser's attestation response and, on success,
    stores the new credential. Always emails the account (see
    send_webauthn_credential_added_email's docstring for why this
    matters even though the action already required a valid access
    token).
    """
    existing = await get_user_credentials(db, current_user.id)
    if len(existing) >= settings.WEBAUTHN_MAX_CREDENTIALS_PER_USER:
        raise _TOO_MANY_CREDENTIALS

    try:
        verification = await verify_registration(current_user.id, payload.credential)
    except WebAuthnException as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=f"Registration verification failed: {exc}")

    transports = payload.credential.get("response", {}).get("transports") or []
    credential = WebAuthnCredential(
        user_id=current_user.id,
        credential_id=verification.credential_id,
        public_key=verification.credential_public_key,
        sign_count=verification.sign_count,
        transports=",".join(transports) if transports else None,
        nickname=payload.nickname,
    )
    db.add(credential)
    await log_audit_action(
        db, user_id=current_user.id, action=AuditAction.WEBAUTHN_CREDENTIAL_ADDED, ip=client_ip(request),
        user_agent=request.headers.get("user-agent"), success=True, metadata={"nickname": payload.nickname},
    )
    await db.commit()

    try:
        send_webauthn_credential_added_email(current_user.email, payload.nickname)
    except (EnvironmentError, RuntimeError) as exc:
        logger.warning("failed to send webauthn-credential-added notification to %s: %s", current_user.email, exc)

    return WebAuthnCredentialEntry.model_validate(credential)


@router.get("/credentials", response_model=WebAuthnCredentialListResponse)
async def list_webauthn_credentials(
    current_user: User = Depends(get_current_user_any_consent_status), db: AsyncSession = Depends(get_db),
):
    credentials = await get_user_credentials(db, current_user.id)
    return WebAuthnCredentialListResponse(items=[WebAuthnCredentialEntry.model_validate(c) for c in credentials])


@router.delete("/credentials/{credential_id}")
async def delete_webauthn_credential(
    credential_id: uuid.UUID, request: Request,
    current_user: User = Depends(get_current_user_any_consent_status), db: AsyncSession = Depends(get_db),
):
    """
    Removing a lost/retired key. Scoped by user_id in the WHERE clause,
    not just the credential's own id, for the same reason
    DELETE /sessions/{id} is (api/routers/sessions.py): a credential id
    belonging to someone else must 404, not reveal it exists at all.
    Always emails the account, same reasoning as registration -- see
    send_webauthn_credential_removed_email's docstring.
    """
    credentials = await get_user_credentials(db, current_user.id)
    target = next((c for c in credentials if c.id == credential_id), None)
    if target is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Not found")

    await db.execute(delete(WebAuthnCredential).where(WebAuthnCredential.id == target.id))
    await log_audit_action(
        db, user_id=current_user.id, action=AuditAction.WEBAUTHN_CREDENTIAL_REMOVED, ip=client_ip(request),
        user_agent=request.headers.get("user-agent"), success=True, metadata={"nickname": target.nickname},
    )
    await db.commit()

    try:
        send_webauthn_credential_removed_email(current_user.email, target.nickname)
    except (EnvironmentError, RuntimeError) as exc:
        logger.warning("failed to send webauthn-credential-removed notification to %s: %s", current_user.email, exc)

    return {"message": "Security key removed"}


@router.post("/authenticate/options")
async def webauthn_authentication_options(payload: WebAuthnAuthenticationOptionsRequest, db: AsyncSession = Depends(get_db)):
    """
    Step 1 of the login-time second factor -- parallels
    api/routers/two_factor.py's /verify-login. Takes the same mfa_token
    POST /auth/login already returned; not rate-limited itself (it
    checks no secret, same reasoning as /auth/2fa/setup not being
    rate-limited while /enable is), but the mfa_token must still decode
    to a real, currently-pending login.
    """
    unauthorized = HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid or expired MFA session, please log in again")
    try:
        user_id = decode_token(payload.mfa_token, TokenPurpose.MFA_PENDING).user_id
    except (ExpiredSignatureError, InvalidTokenError, InvalidTokenPurposeError):
        raise unauthorized

    credentials = await get_user_credentials(db, user_id)
    if not credentials:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="This account has no registered security keys")

    options_json = await build_authentication_options(hash_token(payload.mfa_token), credentials)
    return Response(content=options_json, media_type="application/json")


@router.post("/authenticate/verify", response_model=TokenResponse)
async def webauthn_authentication_verify(
    payload: WebAuthnAuthenticationVerifyRequest, request: Request, response: Response, db: AsyncSession = Depends(get_db),
):
    """
    Step 2: verifies the assertion and, if valid, issues the real
    session -- exactly parallel to
    api/routers/two_factor.py's verify_two_factor_login. Rate-limited by
    the hashed mfa_token, same reasoning and same threshold as that
    endpoint: caps how many forged/replayed assertions can be tried
    against one pending login before it must be restarted from
    /auth/login.
    """
    await enforce_rate_limit(
        f"ratelimit:webauthn-verify:token:{hash_token(payload.mfa_token)}",
        settings.TWO_FA_VERIFY_RATE_LIMIT_MAX_ATTEMPTS, settings.TWO_FA_VERIFY_RATE_LIMIT_WINDOW_SECONDS,
    )

    unauthorized = HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid or expired MFA session, please log in again")
    try:
        user_id = decode_token(payload.mfa_token, TokenPurpose.MFA_PENDING).user_id
    except (ExpiredSignatureError, InvalidTokenError, InvalidTokenPurposeError):
        raise unauthorized

    user = await db.get(User, user_id)
    if user is None or not user.is_active or user.is_deleted:
        raise unauthorized

    raw_id = payload.credential.get("rawId") or payload.credential.get("id")
    credential_id_bytes = base64url_to_bytes(raw_id) if isinstance(raw_id, str) else None

    # Scoped to THIS user's own credentials -- a credential id belonging
    # to a different account must never be usable to complete someone
    # else's pending login, even if the raw assertion were somehow valid
    # (it can't be, since the public key wouldn't match -- this check is
    # a cheap first line of defense that also gives a clean 401 instead
    # of a confusing verification-library error).
    stored_credential = next(
        (c for c in await get_user_credentials(db, user_id) if c.credential_id == credential_id_bytes), None,
    )
    if stored_credential is None:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Unrecognized security key for this account")

    try:
        verification = await verify_authentication(hash_token(payload.mfa_token), payload.credential, stored_credential)
    except WebAuthnException:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Security key verification failed")

    stored_credential.sign_count = verification.new_sign_count
    stored_credential.last_used_at = dt.datetime.now(dt.timezone.utc)

    # Same "proof the real owner still controls a second factor" logic
    # as api/routers/two_factor.py's _cancel_pending_lockout_recovery --
    # duplicated narrowly here rather than imported (that function is a
    # private, TOTP-scoped helper) to avoid coupling this router to
    # two_factor.py for four lines.
    await db.execute(
        delete(TwoFactorLockoutRecoveryToken).where(
            TwoFactorLockoutRecoveryToken.user_id == user.id, TwoFactorLockoutRecoveryToken.used_at.is_(None)
        )
    )

    await log_audit_action(
        db, user_id=user.id, action=AuditAction.WEBAUTHN_LOGIN_SUCCESS, ip=client_ip(request),
        user_agent=request.headers.get("user-agent"), success=True, metadata={"credential_id": str(stored_credential.id)},
    )

    tokens = await issue_session(db, response, request, user.id, notify_new_device_email=user.email)
    await db.commit()
    return tokens
