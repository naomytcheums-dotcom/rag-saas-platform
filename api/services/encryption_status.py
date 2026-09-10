"""Partie 10.3 -- status/rotation service backing GET/POST /encryption/*."""

import uuid

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from api.config import settings
from api.models.encryption_audit import EncryptionAudit
from api.models.webhook import Webhook
from api.security.encryption import EncryptionNotConfiguredError, decrypt_data, encrypt_data, hash_data, verify_hash


async def get_encryption_status(db: AsyncSession) -> dict:
    encrypted_webhook_secrets = await db.scalar(
        select(func.count()).select_from(Webhook).where(Webhook.secret.is_not(None))
    ) or 0
    last_rotation = await db.scalar(
        select(EncryptionAudit).where(EncryptionAudit.operation == "rotate_keys", EncryptionAudit.success.is_(True))
        .order_by(EncryptionAudit.created_at.desc()).limit(1)
    )
    return {
        "enabled": bool(settings.ENCRYPTION_MASTER_KEY),
        "algorithm": settings.ENCRYPTION_ALGORITHM,
        "key_storage": settings.ENCRYPTION_KEY_STORAGE,
        "encrypted_fields": ["Webhook.secret", "SlackIntegration.bot_token", "SlackIntegration.user_token", "TeamsIntegration.bot_token", "DiscordIntegration.bot_token", "JWTSigningKey.secret (Fernet)", "EnterpriseSSOConnection.client_secret (Fernet)"],
        "encrypted_row_count": encrypted_webhook_secrets,
        "previous_key_configured": bool(settings.ENCRYPTION_MASTER_KEY_PREVIOUS),
        "last_rotation_at": last_rotation.created_at if last_rotation else None,
    }


async def rotate_encryption_keys(db: AsyncSession, *, performed_by: uuid.UUID) -> dict:
    """Real re-encryption pass: walks every Webhook.secret and re-writes
    it under the CURRENT ENCRYPTION_MASTER_KEY. Meaningful specifically
    when an operator has just rotated the env var (set a new
    ENCRYPTION_MASTER_KEY, moved the old one to
    ENCRYPTION_MASTER_KEY_PREVIOUS, and restarted) -- this finishes that
    rotation by making every row decryptable under the NEW key alone,
    after which ENCRYPTION_MASTER_KEY_PREVIOUS can be safely removed.
    Idempotent: re-running it after it already succeeded just
    re-encrypts already-current-key rows with a fresh nonce, which is
    harmless."""
    if not settings.ENCRYPTION_MASTER_KEY:
        raise EncryptionNotConfiguredError("ENCRYPTION_MASTER_KEY is not set")

    rows = list((await db.scalars(select(Webhook).where(Webhook.secret.is_not(None)))).all())
    rotated = 0
    for webhook in rows:
        plaintext = decrypt_data(webhook.secret)
        webhook.secret = encrypt_data(plaintext)
        rotated += 1

    audit = EncryptionAudit(operation="rotate_keys", rows_affected=rotated, success=True, detail=f"Re-encrypted {rotated} webhook secret(s)", performed_by=performed_by)
    db.add(audit)
    await db.flush()
    return {"rotated_rows": rotated, "rotated_at": audit.created_at}


def test_encryption_roundtrip() -> dict:
    """POST /encryption/test -- a real encrypt->decrypt->hash->verify
    round-trip against a throwaway value, never touching real data."""
    sample = f"encryption-self-test-{uuid.uuid4()}"
    encrypted = encrypt_data(sample)
    decrypted = decrypt_data(encrypted)
    digest = hash_data(sample)
    return {
        "roundtrip_ok": decrypted == sample,
        "hash_verification_ok": verify_hash(sample, digest),
        "algorithm": settings.ENCRYPTION_ALGORITHM,
    }
