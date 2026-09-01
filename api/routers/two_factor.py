"""
1.1.7 -- TOTP setup/enable/disable, plus the login-time verification step
that auth.py's /auth/login hands off to when totp_enabled is True.

/setup only stores a *pending* secret -- totp_enabled stays False until
/enable proves the user actually scanned the QR code and their
authenticator app produces matching codes. Skipping that proof would let a
setup call that's never followed through lock nothing, but also means a
user could think 2FA is on when it isn't; requiring /enable's confirmation
avoids that false sense of security.
"""

from fastapi import APIRouter, Depends, HTTPException, Request, Response, status
from jwt import ExpiredSignatureError, InvalidTokenError
from sqlalchemy.ext.asyncio import AsyncSession

from api.dependencies import get_current_user, get_db
from api.models.user import User
from api.schemas.auth import MessageResponse, TokenResponse, TwoFactorCodeRequest, TwoFactorSetupResponse, TwoFactorVerifyLoginRequest
from api.security.jwt import InvalidTokenPurposeError, TokenPurpose, decode_token
from api.security.sessions import issue_session
from api.security.totp import generate_totp_secret, totp_provisioning_qr_data_uri, verify_totp_code

router = APIRouter(prefix="/auth/2fa", tags=["auth"])


@router.post("/setup", response_model=TwoFactorSetupResponse)
async def setup_two_factor(current_user: User = Depends(get_current_user), db: AsyncSession = Depends(get_db)):
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


@router.post("/enable", response_model=MessageResponse)
async def enable_two_factor(payload: TwoFactorCodeRequest, current_user: User = Depends(get_current_user), db: AsyncSession = Depends(get_db)):
    """
    Step 2: proves the user actually scanned the QR code from /setup by
    submitting the current 6-digit code their authenticator app is now
    showing. Only once that code checks out does totp_enabled flip to
    True -- from this point on, password login alone is not enough (see
    auth.py's login() and /verify-login below).
    """
    if not current_user.totp_secret:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Call /auth/2fa/setup first")
    if not verify_totp_code(current_user.totp_secret, payload.code):
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Invalid code")

    current_user.totp_enabled = True
    await db.commit()
    return MessageResponse(message="Two-factor authentication enabled")


@router.post("/disable", response_model=MessageResponse)
async def disable_two_factor(payload: TwoFactorCodeRequest, current_user: User = Depends(get_current_user), db: AsyncSession = Depends(get_db)):
    """
    Turns 2FA back off -- still requires a valid current code, not just
    the access token, so someone who stole a logged-in session/laptop
    can't disable the extra protection without also having the physical
    authenticator device.
    """
    if not current_user.totp_enabled or not current_user.totp_secret:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Two-factor authentication is not enabled")
    if not verify_totp_code(current_user.totp_secret, payload.code):
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Invalid code")

    current_user.totp_enabled = False
    current_user.totp_secret = None
    await db.commit()
    return MessageResponse(message="Two-factor authentication disabled")


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
    """
    unauthorized = HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid or expired MFA session, please log in again")
    try:
        user_id = decode_token(payload.mfa_token, TokenPurpose.MFA_PENDING)
    except (ExpiredSignatureError, InvalidTokenError, InvalidTokenPurposeError):
        raise unauthorized

    user = await db.get(User, user_id)
    if user is None or not user.is_active or user.is_deleted or not user.totp_enabled or not user.totp_secret:
        raise unauthorized
    if not verify_totp_code(user.totp_secret, payload.code):
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid code")

    tokens = await issue_session(db, response, request, user.id)
    await db.commit()
    return tokens
