"""
BYOK (Bring Your Own Key) -- lets an organization use its own LLM
provider API key instead of this platform's own `.env`-configured one.
Real, immediate effect: `resolve_org_api_key` is called from
`api/services/agent_orchestrator.py` right before each real LLM call,
and a resolved key is passed straight through as `chat_completion`'s own
`api_key=` override (already supported, `_chat_completion_raw`'s own
`call_kwargs.update(kwargs)` -- a real, explicit caller override always
wins, see api/services/llm_providers.py). An organization using BYOK for
a provider is never charged platform AI credits for that provider's
calls -- it's their own key, their own bill with that provider.
"""

import uuid

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from api.models.organization_llm_config import OrganizationLLMConfig
from api.security.secret_encryption import decrypt_secret, encrypt_secret
from api.services.llm_providers import PROVIDER_SETTINGS


class UnknownLLMProviderError(Exception):
    pass


async def get_org_llm_config(db: AsyncSession, organization_id: uuid.UUID, provider: str) -> OrganizationLLMConfig | None:
    return await db.scalar(
        select(OrganizationLLMConfig).where(
            OrganizationLLMConfig.organization_id == organization_id,
            OrganizationLLMConfig.provider == provider,
            OrganizationLLMConfig.is_active.is_(True),
        )
    )


async def list_org_llm_configs(db: AsyncSession, organization_id: uuid.UUID) -> list[OrganizationLLMConfig]:
    return list((await db.scalars(
        select(OrganizationLLMConfig).where(OrganizationLLMConfig.organization_id == organization_id)
    )).all())


async def set_org_llm_config(
    db: AsyncSession, organization_id: uuid.UUID, provider: str, api_key: str, *, created_by: uuid.UUID | None = None,
) -> OrganizationLLMConfig:
    """Upsert -- a second BYOK submission for the same provider replaces
    the stored key rather than creating a duplicate row (the real,
    unique (organization_id, provider) constraint, migration 0109,
    already enforces one row per provider)."""
    if provider not in PROVIDER_SETTINGS:
        raise UnknownLLMProviderError(f"Unknown LLM provider: {provider!r} (expected one of {sorted(PROVIDER_SETTINGS)})")

    existing = await db.scalar(
        select(OrganizationLLMConfig).where(
            OrganizationLLMConfig.organization_id == organization_id, OrganizationLLMConfig.provider == provider,
        )
    )
    encrypted = encrypt_secret(api_key)
    if existing is not None:
        existing.encrypted_api_key = encrypted
        existing.is_active = True
        await db.flush()
        return existing

    row = OrganizationLLMConfig(organization_id=organization_id, provider=provider, encrypted_api_key=encrypted, created_by=created_by)
    db.add(row)
    await db.flush()
    return row


async def delete_org_llm_config(db: AsyncSession, organization_id: uuid.UUID, provider: str) -> bool:
    config = await db.scalar(
        select(OrganizationLLMConfig).where(
            OrganizationLLMConfig.organization_id == organization_id, OrganizationLLMConfig.provider == provider,
        )
    )
    if config is None:
        return False
    await db.delete(config)
    await db.flush()
    return True


async def resolve_org_api_key(db: AsyncSession, organization_id: uuid.UUID, provider: str) -> str | None:
    """None when the organization has no active BYOK key for `provider`
    -- the real, honest signal for "use the platform's own key" (never a
    fabricated fallback key)."""
    config = await get_org_llm_config(db, organization_id, provider)
    if config is None:
        return None
    return decrypt_secret(config.encrypted_api_key)
