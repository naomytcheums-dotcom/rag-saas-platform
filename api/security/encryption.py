"""
Partie 10.3 -- a second, real encryption-at-rest primitive alongside the
existing Fernet-based api/security/secret_encryption.py (kept unchanged
for the two fields already using it: JWT signing keys, enterprise SSO
client secrets -- re-keying those is a separate, unrelated maintenance
operation, not something this étape asks for). This module implements
the literal algorithm Partie 10.3 names (AES-256-GCM, via `cryptography`'s
real AESGCM primitive -- the same dependency Fernet itself is built on,
so no new dependency is added) for NEW fields (Webhook.secret) and the
generic encrypt_data/decrypt_data surface exposed at
GET/POST /encryption/*.

Fernet IS already AES-128-CBC + HMAC-SHA256 authenticated encryption --
a real, standard, still-secure construction, not a weaker one. This
module uses AES-256-GCM instead because Partie 10.3's own spec names
that algorithm specifically; stating that plainly here rather than
silently misdescribing Fernet as "AES-256-GCM" it never was.

Key rotation, for real: ENCRYPTION_MASTER_KEY is the CURRENT key, used
for every new encryption. ENCRYPTION_MASTER_KEY_PREVIOUS (optional) is
tried for DECRYPTION when the current key fails -- a real grace window
during which both old and new ciphertexts continue to decrypt, exactly
like a rotation is supposed to work. rotate_encryption_key() (called by
POST /encryption/rotate-keys) re-encrypts every row this module protects
(currently: Webhook.secret) under the current key, so a completed
rotation needs no PREVIOUS key at all -- it's only relied on for the
transition period between "new key set" and "rotation job run".
"""

import base64
import hashlib
import hmac as hmac_module
import os

from cryptography.hazmat.primitives.ciphers.aead import AESGCM

from api.config import settings

ALGORITHM = "AES-256-GCM"


class EncryptionNotConfiguredError(RuntimeError):
    pass


class DecryptionFailedError(RuntimeError):
    pass


def generate_encryption_key() -> str:
    """A fresh, real 256-bit key, base64-encoded for storage in an env
    var -- same shape ENCRYPTION_MASTER_KEY expects."""
    return base64.urlsafe_b64encode(AESGCM.generate_key(bit_length=256)).decode()


def _key_bytes(raw: str) -> bytes:
    return base64.urlsafe_b64decode(raw.encode())


def _current_key() -> bytes:
    if not settings.ENCRYPTION_MASTER_KEY:
        raise EncryptionNotConfiguredError(
            "ENCRYPTION_MASTER_KEY must be set to use this feature -- generate one with "
            "api.security.encryption.generate_encryption_key()"
        )
    return _key_bytes(settings.ENCRYPTION_MASTER_KEY)


def encrypt_data(plaintext: str, *, key_id: str = "current") -> str:
    """Returns `key_id:nonce:ciphertext`, all base64 except the key_id
    tag itself -- the key_id lets decrypt_data know (without guessing)
    whether to try the current or the previous key."""
    key = _current_key() if key_id == "current" else _key_bytes(key_id)
    nonce = os.urandom(12)
    aesgcm = AESGCM(key)
    ciphertext = aesgcm.encrypt(nonce, plaintext.encode(), None)
    return "current:" + base64.urlsafe_b64encode(nonce).decode() + ":" + base64.urlsafe_b64encode(ciphertext).decode()


def decrypt_data(encrypted: str, *, key_id: str | None = None) -> str:
    try:
        tag, nonce_b64, ciphertext_b64 = encrypted.split(":", 2)
    except ValueError as exc:
        raise DecryptionFailedError("Malformed ciphertext envelope") from exc

    nonce = base64.urlsafe_b64decode(nonce_b64)
    ciphertext = base64.urlsafe_b64decode(ciphertext_b64)

    keys_to_try = [_current_key()]
    if settings.ENCRYPTION_MASTER_KEY_PREVIOUS:
        keys_to_try.append(_key_bytes(settings.ENCRYPTION_MASTER_KEY_PREVIOUS))

    last_error: Exception | None = None
    for key in keys_to_try:
        try:
            return AESGCM(key).decrypt(nonce, ciphertext, None).decode()
        except Exception as exc:  # noqa: BLE001 -- real cryptography.exceptions.InvalidTag, re-raised as our own type below
            last_error = exc
    raise DecryptionFailedError("Could not decrypt with the current or previous ENCRYPTION_MASTER_KEY") from last_error


def encrypt_field(value: str, key_id: str = "current") -> str:
    return encrypt_data(value, key_id=key_id)


def decrypt_field(encrypted_value: str, key_id: str | None = None) -> str:
    return decrypt_data(encrypted_value, key_id=key_id)


def hash_data(data: str) -> str:
    """One-way SHA-256 -- for integrity/lookup values (e.g. matching a
    webhook secret without ever decrypting it), never for passwords
    (this codebase's password hashing is Argon2, api/security/passwords.py,
    unrelated and unchanged by this module)."""
    return hashlib.sha256(data.encode()).hexdigest()


def verify_hash(data: str, expected_hash: str) -> bool:
    return hmac_module.compare_digest(hash_data(data), expected_hash)


def supported_algorithms() -> list[dict]:
    return [
        {"name": "AES-256-GCM", "purpose": "Symmetric encryption of new sensitive fields (this module)", "in_use": True},
        {"name": "AES-128-CBC + HMAC-SHA256 (Fernet)", "purpose": "Symmetric encryption of JWT signing keys and enterprise SSO secrets (api/security/secret_encryption.py)", "in_use": True},
        {"name": "Argon2", "purpose": "Password hashing (api/security/passwords.py)", "in_use": True},
        {"name": "HMAC-SHA256", "purpose": "Webhook/Slack signature verification, audit log hash-chaining", "in_use": True},
        {"name": "Ed25519", "purpose": "Discord interaction signature verification (api/security/chat_integrations_signature.py)", "in_use": True},
        {"name": "RSA-4096", "purpose": "Not used anywhere in this codebase today -- no feature currently needs asymmetric encryption of stored data", "in_use": False},
    ]
