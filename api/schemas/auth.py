"""Request/response bodies for api/routers/auth.py, password.py, verify.py, two_factor.py."""

from typing import Literal

from pydantic import BaseModel, EmailStr, Field, field_validator

# bcrypt silently ignores any byte past position 72 -- rejecting a longer
# password here is better than letting two different long passwords that
# share the same first 72 bytes both "work" for the same account.
_BCRYPT_MAX_BYTES = 72


class RegisterRequest(BaseModel):
    """Body of POST /auth/register."""

    email: EmailStr
    password: str = Field(min_length=8)
    full_name: str | None = None
    company: str | None = None
    accept_terms: bool  # must be True -- validated below; False is rejected before the account is ever created

    @field_validator("password")
    @classmethod
    def _password_within_bcrypt_limit(cls, value: str) -> str:
        if len(value.encode("utf-8")) > _BCRYPT_MAX_BYTES:
            raise ValueError(f"password must be at most {_BCRYPT_MAX_BYTES} bytes")
        return value

    @field_validator("accept_terms")
    @classmethod
    def _terms_must_be_accepted(cls, value: bool) -> bool:
        if not value:
            raise ValueError("you must accept the terms of service to register")
        return value


class LoginRequest(BaseModel):
    """Body of POST /auth/login."""

    email: EmailStr
    password: str


class TokenResponse(BaseModel):
    """
    Successful-login shape, returned by /auth/register, /auth/login (when
    2FA isn't enabled), /auth/refresh, and /auth/2fa/verify-login. The
    refresh token itself is never in this body -- it's set as an httpOnly
    cookie by the same response, see api/security/sessions.py.
    """

    access_token: str
    token_type: Literal["bearer"] = "bearer"
    expires_in: int  # seconds until access_token expires -- lets the frontend schedule its own refresh proactively


class MFARequiredResponse(BaseModel):
    """
    Returned by POST /auth/login instead of TokenResponse when the
    account has 2FA enabled -- no tokens yet. The frontend must follow up
    with POST /auth/2fa/verify-login, passing mfa_token back along with
    the 6-digit code from the user's authenticator app.
    """

    mfa_required: Literal[True] = True
    mfa_token: str


class TwoFactorVerifyLoginRequest(BaseModel):
    """Body of POST /auth/2fa/verify-login -- the second half of logging
    into a 2FA-enabled account, see MFARequiredResponse above."""

    mfa_token: str
    code: str = Field(min_length=6, max_length=6)


class PasswordForgotRequest(BaseModel):
    """Body of POST /auth/password/forgot."""

    email: EmailStr


class PasswordResetRequest(BaseModel):
    """Body of POST /auth/password/reset -- `token` is the raw value from
    the link emailed by /auth/password/forgot."""

    token: str
    new_password: str = Field(min_length=8)

    @field_validator("new_password")
    @classmethod
    def _password_within_bcrypt_limit(cls, value: str) -> str:
        if len(value.encode("utf-8")) > _BCRYPT_MAX_BYTES:
            raise ValueError(f"password must be at most {_BCRYPT_MAX_BYTES} bytes")
        return value


class TwoFactorLockoutRecoveryRequest(BaseModel):
    """Body of POST /auth/2fa/lockout-recovery/request -- the last resort
    for a user who has lost both their authenticator device and every
    recovery code. Takes the account password (not just the email) since
    this is a stronger claim than "I can read this mailbox"."""

    email: EmailStr
    password: str


class TwoFactorLockoutRecoveryConfirmRequest(BaseModel):
    """Body of POST /auth/2fa/lockout-recovery/confirm -- `token` is the
    raw value from the link emailed by /lockout-recovery/request. Only
    valid once TWO_FA_LOCKOUT_RECOVERY_DELAY_HOURS have passed since the
    request, see that endpoint's docstring."""

    token: str


class AccountRestoreRequest(BaseModel):
    """Body of POST /account/restore/request -- public (no access token:
    the account is deactivated), same shape as PasswordForgotRequest."""

    email: EmailStr


class AccountRestoreConfirmRequest(BaseModel):
    """Body of POST /account/restore/confirm -- `token` is the raw value
    from the link emailed by /account/restore/request."""

    token: str


class EmailVerifyConfirmRequest(BaseModel):
    """Body of POST /auth/verify-email/confirm -- the 6-digit code from
    the verification email."""

    code: str = Field(min_length=6, max_length=6)


class TwoFactorSetupResponse(BaseModel):
    """
    Returned by POST /auth/2fa/setup. `secret` is the raw TOTP secret
    (for an app that wants manual text entry); `qr_code_data_uri` is the
    same secret encoded as a scannable QR code, ready to drop into an
    <img src="..."> tag as-is.
    """

    secret: str
    qr_code_data_uri: str


class TwoFactorCodeRequest(BaseModel):
    """Body of POST /auth/2fa/enable and /auth/2fa/disable -- the current
    6-digit code from the user's authenticator app."""

    code: str = Field(min_length=6, max_length=6)


class TwoFactorRecoveryCodesResponse(BaseModel):
    """
    Returned by POST /auth/2fa/enable and POST /auth/2fa/recovery-codes/regenerate --
    the only two moments these codes are ever shown in plaintext. The
    frontend must display these once and tell the user to store them
    somewhere safe (password manager, printed copy): they cannot be
    retrieved again after this response, only invalidated and replaced.
    """

    recovery_codes: list[str]


class TwoFactorRecoveryCodeLoginRequest(BaseModel):
    """Body of POST /auth/2fa/verify-recovery-code -- the fallback path
    for a user who has lost access to their authenticator app, using one
    of the single-use codes from TwoFactorRecoveryCodesResponse instead
    of a 6-digit TOTP code."""

    mfa_token: str
    recovery_code: str


class MessageResponse(BaseModel):
    """Generic {"message": "..."} shape for endpoints that don't need to
    return any real data, just confirm what happened."""

    message: str
