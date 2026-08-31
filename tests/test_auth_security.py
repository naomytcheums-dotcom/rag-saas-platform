"""Unit tests for api/security/{hashing,jwt,totp}.py -- the pure logic
underneath the auth routers, tested in isolation same as the rest of this
project's src/ modules."""

import datetime as dt
import uuid

import jwt as pyjwt
import pyotp
import pytest

from api.config import settings
from api.security.hashing import generate_otp_code, generate_raw_token, hash_password, hash_token, verify_password
from api.security.jwt import (
    InvalidTokenPurposeError,
    TokenPurpose,
    create_access_token,
    create_mfa_pending_token,
    decode_token,
)
from api.security.totp import generate_totp_secret, totp_provisioning_qr_data_uri, verify_totp_code


def test_password_hash_roundtrip():
    hashed = hash_password("correct-horse-battery-staple")
    assert hashed != "correct-horse-battery-staple"
    assert verify_password("correct-horse-battery-staple", hashed)
    assert not verify_password("wrong-password", hashed)


def test_token_hash_is_deterministic_and_one_way():
    raw = generate_raw_token()
    assert hash_token(raw) == hash_token(raw)
    assert hash_token(raw) != raw


def test_generate_raw_token_is_unique():
    assert generate_raw_token() != generate_raw_token()


def test_generate_otp_code_is_six_digits():
    code = generate_otp_code()
    assert len(code) == 6
    assert code.isdigit()


def test_access_token_roundtrip():
    user_id = uuid.uuid4()
    token = create_access_token(user_id)
    assert decode_token(token, TokenPurpose.ACCESS) == user_id


def test_access_token_rejected_for_wrong_purpose():
    user_id = uuid.uuid4()
    mfa_token = create_mfa_pending_token(user_id)
    with pytest.raises(InvalidTokenPurposeError):
        decode_token(mfa_token, TokenPurpose.ACCESS)


def test_expired_access_token_is_rejected():
    now = dt.datetime.now(dt.timezone.utc)
    expired = pyjwt.encode(
        {"sub": str(uuid.uuid4()), "purpose": TokenPurpose.ACCESS.value, "iat": now - dt.timedelta(hours=1), "exp": now - dt.timedelta(minutes=1)},
        settings.JWT_SECRET_KEY,
        algorithm=settings.JWT_ALGORITHM,
    )
    with pytest.raises(pyjwt.ExpiredSignatureError):
        decode_token(expired, TokenPurpose.ACCESS)


def test_totp_enrollment_and_verification():
    secret = generate_totp_secret()
    valid_code = pyotp.TOTP(secret).now()
    wrong_code = "000000" if valid_code != "000000" else "111111"

    assert verify_totp_code(secret, valid_code)
    assert not verify_totp_code(secret, wrong_code)


def test_totp_qr_is_a_png_data_uri():
    secret = generate_totp_secret()
    uri = totp_provisioning_qr_data_uri(secret, "ada@example.com")
    assert uri.startswith("data:image/png;base64,")
