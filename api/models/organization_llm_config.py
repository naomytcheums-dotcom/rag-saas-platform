"""
BYOK (Bring Your Own Key) -- an organization's own LLM provider API key,
used instead of this platform's own (`.env`-configured) key for that
organization's real LLM calls. One row per (organization, provider):
an organization can BYOK one provider (e.g. its own OpenAI key) while
still using the platform's included credits for another.

The key itself is never stored in plaintext -- `encrypted_api_key`
holds the real Fernet ciphertext from api/security/secret_encryption.py,
the same shared encryption-at-rest primitive already used for JWT
signing keys and enterprise SSO client secrets (that module's own
docstring). Reused deliberately rather than a second, bespoke scheme:
same real security property (a stolen DB dump alone can't recover the
key), one audited implementation instead of two.
"""

import datetime as dt
import uuid

from sqlalchemy import Boolean, DateTime, ForeignKey, String, UniqueConstraint, func
from sqlalchemy.orm import Mapped, mapped_column

from api.database import Base


class OrganizationLLMConfig(Base):
    __tablename__ = "organization_llm_configs"

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    organization_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("organizations.id", ondelete="CASCADE"), nullable=False, index=True)
    provider: Mapped[str] = mapped_column(String(50), nullable=False)
    encrypted_api_key: Mapped[str] = mapped_column(String(1000), nullable=False)
    is_active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    created_by: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("users.id", ondelete="SET NULL"), nullable=True)
    created_at: Mapped[dt.datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[dt.datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())

    __table_args__ = (
        UniqueConstraint("organization_id", "provider", name="uq_organization_llm_config_org_provider"),
    )
