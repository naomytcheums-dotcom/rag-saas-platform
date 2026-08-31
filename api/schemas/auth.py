"""Request/response bodies for api/routers/auth.py, password.py, verify.py, two_factor.py."""

from typing import Literal

from pydantic import BaseModel, EmailStr, Field, field_validator

# bcrypt silently ignores any byte past position 72 -- rejecting a longer
# password here is better than letting two different long passwords that
# share the same first 72 bytes both "work" for the same account.
_BCRYPT_MAX_BYTES = 72


class RegisterRequest(BaseModel):
    email: EmailStr
    password: str = Field(min_length=8)
    full_name: str | None = None
    company: str | None = None
    accept_terms: bool

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
    email: EmailStr
    password: str


class TokenResponse(BaseModel):
    access_token: str
    token_type: Literal["bearer"] = "bearer"
    expires_in: int


class MFARequiredResponse(BaseModel):
    mfa_required: Literal[True] = True
    mfa_token: str


class TwoFactorVerifyLoginRequest(BaseModel):
    mfa_token: str
    code: str = Field(min_length=6, max_length=6)


class PasswordForgotRequest(BaseModel):
    email: EmailStr


class PasswordResetRequest(BaseModel):
    token: str
    new_password: str = Field(min_length=8)

    @field_validator("new_password")
    @classmethod
    def _password_within_bcrypt_limit(cls, value: str) -> str:
        if len(value.encode("utf-8")) > _BCRYPT_MAX_BYTES:
            raise ValueError(f"password must be at most {_BCRYPT_MAX_BYTES} bytes")
        return value


class EmailVerifyConfirmRequest(BaseModel):
    code: str = Field(min_length=6, max_length=6)


class TwoFactorSetupResponse(BaseModel):
    secret: str
    qr_code_data_uri: str


class TwoFactorCodeRequest(BaseModel):
    code: str = Field(min_length=6, max_length=6)


class MessageResponse(BaseModel):
    message: str
