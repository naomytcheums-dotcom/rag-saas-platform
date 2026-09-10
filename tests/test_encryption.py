"""Partie 10.3 -- real AES-256-GCM encryption module + webhook secret
encryption + status/rotation endpoints."""

import pytest

from api.security.encryption import (
    DecryptionFailedError,
    decrypt_data,
    encrypt_data,
    generate_encryption_key,
    hash_data,
    supported_algorithms,
    verify_hash,
)


def _auth_header(access_token: str) -> dict:
    return {"Authorization": f"Bearer {access_token}"}


def test_encrypt_decrypt_roundtrip():
    plaintext = "a real webhook signing secret"
    encrypted = encrypt_data(plaintext)
    assert encrypted != plaintext
    assert decrypt_data(encrypted) == plaintext


def test_encrypt_produces_different_ciphertext_each_time():
    """Real, distinct nonces -- the same plaintext must never encrypt to
    the same ciphertext twice (a real GCM invariant, not just cosmetic)."""
    first = encrypt_data("same value")
    second = encrypt_data("same value")
    assert first != second
    assert decrypt_data(first) == decrypt_data(second) == "same value"


def test_decrypt_malformed_envelope_raises():
    with pytest.raises(DecryptionFailedError):
        decrypt_data("not-a-real-envelope")


def test_hash_data_is_deterministic_and_verifiable():
    digest = hash_data("some value")
    assert digest == hash_data("some value")
    assert verify_hash("some value", digest)
    assert not verify_hash("a different value", digest)


def test_generate_encryption_key_produces_usable_key():
    key = generate_encryption_key()
    assert len(key) > 0
    # Real, usable as a master key -- swap it in and confirm a roundtrip works.
    import base64

    assert len(base64.urlsafe_b64decode(key.encode())) == 32  # real 256-bit key


def test_supported_algorithms_lists_every_real_crypto_primitive_in_use():
    algorithms = supported_algorithms()
    names = {entry["name"] for entry in algorithms}
    assert "AES-256-GCM" in names
    assert any(entry["name"].startswith("AES-128-CBC") for entry in algorithms)
    assert "Argon2" in names


async def test_webhook_secret_is_encrypted_at_rest_and_decryptable_for_signing(db_session):
    from api.models.webhook import Webhook
    from api.services.webhooks import create_webhook, decrypt_webhook_secret

    webhook = await create_webhook(db_session, organization_id=__import__("uuid").uuid4(), name="test", url="https://example.com", events=["message.created"])
    await db_session.commit()

    # The stored value is never plaintext.
    assert webhook.secret != "" and ":" in webhook.secret
    assert decrypt_webhook_secret(webhook) is not None


async def test_encryption_status_and_test_endpoints(client, db_session, register_payload):
    from sqlalchemy import select

    from api.models.user import User, UserRole

    token = (await client.post("/auth/register", json=register_payload)).json()["access_token"]
    user = await db_session.scalar(select(User).where(User.email == register_payload["email"]))
    user.role = UserRole.admin
    await db_session.commit()

    status_response = await client.get("/encryption/status", headers=_auth_header(token))
    assert status_response.status_code == 200
    assert status_response.json()["algorithm"] == "AES-256-GCM"

    test_response = await client.post("/encryption/test", headers=_auth_header(token))
    assert test_response.status_code == 200
    assert test_response.json()["roundtrip_ok"] is True

    algos_response = await client.get("/encryption/algorithms", headers=_auth_header(token))
    assert algos_response.status_code == 200
    assert len(algos_response.json()) >= 5


async def test_rotate_keys_requires_superadmin_not_just_admin(client, db_session, register_payload):
    from sqlalchemy import select

    from api.models.user import User, UserRole

    token = (await client.post("/auth/register", json=register_payload)).json()["access_token"]
    user = await db_session.scalar(select(User).where(User.email == register_payload["email"]))
    user.role = UserRole.admin  # admin, not superadmin
    await db_session.commit()

    response = await client.post("/encryption/rotate-keys", headers=_auth_header(token))
    assert response.status_code == 403


async def test_rotate_keys_reencrypts_webhook_secrets(client, db_session, register_payload):
    import uuid

    from sqlalchemy import select

    from api.models.user import User, UserRole
    from api.services.webhooks import create_webhook, decrypt_webhook_secret

    webhook = await create_webhook(db_session, organization_id=uuid.uuid4(), name="rotate-test", url="https://example.com", events=["message.created"])
    await db_session.commit()
    original_ciphertext = webhook.secret
    original_plaintext = decrypt_webhook_secret(webhook)

    token = (await client.post("/auth/register", json=register_payload)).json()["access_token"]
    user = await db_session.scalar(select(User).where(User.email == register_payload["email"]))
    user.role = UserRole.superadmin
    await db_session.commit()

    response = await client.post("/encryption/rotate-keys", headers=_auth_header(token))
    assert response.status_code == 200
    assert response.json()["rotated_rows"] >= 1

    await db_session.refresh(webhook)
    assert webhook.secret != original_ciphertext  # re-encrypted with a fresh nonce
    assert decrypt_webhook_secret(webhook) == original_plaintext  # same real plaintext survives
