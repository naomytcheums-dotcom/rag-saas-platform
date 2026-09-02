"""
Shared Fernet-based encryption-at-rest for the two audit-Categorie-4
secrets that must live in Postgres rather than a .env file, because their
whole point is to change WITHOUT a redeploy: JWT signing keys
(api/models/jwt_signing_key.py, item 28's automatic rotation) and
enterprise SSO client secrets (api/models/enterprise_sso.py, item 27's
admin-configured per-IdP connections).

One shared SECRET_ENCRYPTION_KEY rather than a separate key per feature:
this is a key-encrypting-key whose own rotation cadence is deliberately
decoupled from either secret it protects underneath it (re-keying it
would mean re-encrypting every existing row -- an out-of-band maintenance
operation, not something either feature's own rotation/admin-configure
flow needs to trigger on its own).
"""

from cryptography.fernet import Fernet, InvalidToken

from api.config import settings


class SecretEncryptionNotConfiguredError(RuntimeError):
    pass


def _fernet() -> Fernet:
    if not settings.SECRET_ENCRYPTION_KEY:
        raise SecretEncryptionNotConfiguredError(
            "SECRET_ENCRYPTION_KEY must be set to use this feature -- generate one with: "
            'python -c "from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())"'
        )
    return Fernet(settings.SECRET_ENCRYPTION_KEY.encode())


def encrypt_secret(plaintext: str) -> str:
    return _fernet().encrypt(plaintext.encode()).decode()


def decrypt_secret(ciphertext: str) -> str:
    try:
        return _fernet().decrypt(ciphertext.encode()).decode()
    except InvalidToken as exc:
        raise SecretEncryptionNotConfiguredError(
            "Could not decrypt a stored secret -- SECRET_ENCRYPTION_KEY may be wrong or may have "
            "changed since this value was encrypted"
        ) from exc
