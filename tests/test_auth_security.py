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
    token, jti = create_access_token(user_id)
    decoded = decode_token(token, TokenPurpose.ACCESS)
    assert decoded.user_id == user_id
    assert decoded.jti == jti


def test_access_token_jti_is_unique_per_token():
    user_id = uuid.uuid4()
    _token1, jti1 = create_access_token(user_id)
    _token2, jti2 = create_access_token(user_id)
    assert jti1 != jti2


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


# ---------------------------------------------------------------- 1.1.15 --
def test_decode_token_accepts_a_token_signed_with_a_previous_key(monkeypatch):
    """Routine key rotation: a token signed with an OLD JWT_SECRET_KEY
    must still verify once that key has been moved into
    JWT_PREVIOUS_SECRET_KEYS, even though NEW tokens are signed with the
    current one."""
    old_key = "old-signing-key-" + "x" * 32
    monkeypatch.setattr(settings, "JWT_SECRET_KEY", old_key)
    user_id = uuid.uuid4()
    token_signed_with_old_key, _jti = create_access_token(user_id)

    new_key = "new-signing-key-" + "y" * 32
    monkeypatch.setattr(settings, "JWT_SECRET_KEY", new_key)
    monkeypatch.setattr(settings, "JWT_PREVIOUS_SECRET_KEYS", old_key)

    decoded = decode_token(token_signed_with_old_key, TokenPurpose.ACCESS)
    assert decoded.user_id == user_id

    # And a BRAND NEW token is signed with the new key, not the old one.
    new_token, _jti2 = create_access_token(user_id)
    assert decode_token(new_token, TokenPurpose.ACCESS).user_id == user_id
    with pytest.raises(pyjwt.InvalidSignatureError):
        pyjwt.decode(new_token, old_key, algorithms=[settings.JWT_ALGORITHM])


def test_decode_token_rejects_a_key_that_was_never_configured(monkeypatch):
    """The leak-response procedure: a token signed with a key that is
    NEITHER the current JWT_SECRET_KEY NOR listed in
    JWT_PREVIOUS_SECRET_KEYS must be rejected outright -- this is what
    makes "just don't list the leaked key" an effective, immediate
    response to a compromised signing key."""
    leaked_key = "leaked-key-" + "z" * 32
    monkeypatch.setattr(settings, "JWT_SECRET_KEY", leaked_key)
    token_signed_with_leaked_key, _jti = create_access_token(uuid.uuid4())

    monkeypatch.setattr(settings, "JWT_SECRET_KEY", "brand-new-key-after-the-leak-" + "w" * 20)
    monkeypatch.setattr(settings, "JWT_PREVIOUS_SECRET_KEYS", "")  # deliberately NOT including leaked_key

    with pytest.raises(pyjwt.InvalidSignatureError):
        decode_token(token_signed_with_leaked_key, TokenPurpose.ACCESS)


def test_jwt_previous_secret_keys_supports_multiple_comma_separated_keys(monkeypatch):
    key_a = "key-a-" + "a" * 32
    key_b = "key-b-" + "b" * 32
    monkeypatch.setattr(settings, "JWT_SECRET_KEY", key_a)
    token_a, _ = create_access_token(uuid.uuid4())
    monkeypatch.setattr(settings, "JWT_SECRET_KEY", key_b)
    token_b, _ = create_access_token(uuid.uuid4())

    monkeypatch.setattr(settings, "JWT_SECRET_KEY", "current-key-" + "c" * 32)
    monkeypatch.setattr(settings, "JWT_PREVIOUS_SECRET_KEYS", f"{key_a},{key_b}")

    assert decode_token(token_a, TokenPurpose.ACCESS) is not None
    assert decode_token(token_b, TokenPurpose.ACCESS) is not None


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
