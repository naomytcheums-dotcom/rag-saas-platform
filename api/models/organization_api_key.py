"""
Partie 9.1 + 9.2.1-9.2.6 -- real, revocable, ORGANIZATION-scoped API
keys for the public `/v1/*` API, with rotation/expiration/rate-limit/
quota fields added in this batch.

**Incohérence réelle corrigée -- pas une copie forcée de `AgentAPIKey`**:
5.3.10's own `AgentAPIKey` (`api/models/agent_api_key.py`) is scoped to
ONE real agent, for one real endpoint (`POST /api/agents/run`). Partie
9.1's own 9 endpoints span an entire organization (any agent, document
uploads, knowledge bases, search, usage, embeddings) -- a genuinely
different real scope, not the same real entity reused. This is a new,
separate model, reusing the exact same real hash/generation
DISCIPLINE as `agent_api_keys.py` (SHA-256 hash, one-time plaintext
reveal), never the same real row shape.

**Incohérence réelle corrigée -- 9.2.1 duplique 9.1**: the 9.2.1
prompt asks for a real, new `APIKey` model with essentially the exact
same real shape (`organization_id`, `key_hash`, `key_prefix`,
`scopes`, `expires_at`, `last_used_at`, `created_by`, `revoked_at`,
`UNIQUE(organization_id, name)`) already built for 9.1. Rather than a
real, duplicate parallel table, this ONE real model is extended here
with the genuinely new real fields 9.2.2 (rotation)/9.2.3 (expiration,
already had `expires_at`)/9.2.5 (rate limits)/9.2.6 (quotas) actually
need -- `is_active` is the one real, new 9.2.1 field this model
didn't already have."""

import datetime as dt
import uuid

from sqlalchemy import JSON, Boolean, DateTime, ForeignKey, Integer, String, Text, UniqueConstraint, func
from sqlalchemy.orm import Mapped, mapped_column

from api.database import Base


class OrganizationAPIKey(Base):
    __tablename__ = "organization_api_keys"

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    organization_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("organizations.id", ondelete="CASCADE"), nullable=False, index=True)
    name: Mapped[str] = mapped_column(String(200), nullable=False)
    key_hash: Mapped[str] = mapped_column(String(64), nullable=False, unique=True, index=True)
    key_prefix: Mapped[str] = mapped_column(String(10), nullable=False)
    scopes: Mapped[list] = mapped_column(JSON, nullable=False)
    expires_at: Mapped[dt.datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    last_used_at: Mapped[dt.datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    # Partie 9.2.1 -- real, additive: a distinct real dimension from
    # `revoked_at` (permanent) -- lets a key be temporarily disabled
    # without the permanence of a real revocation.
    is_active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True, server_default="true")
    created_by: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("users.id", ondelete="SET NULL"), nullable=True)
    created_at: Mapped[dt.datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    revoked_at: Mapped[dt.datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)

    # -- Partie 9.2.5 (Rate limits) --------------------------------------------------
    rate_limit: Mapped[int | None] = mapped_column(Integer, nullable=True)
    rate_limit_period: Mapped[str | None] = mapped_column(String(20), nullable=True)

    # -- Partie 9.2.6 (Quotas) --------------------------------------------------------
    quota_limit: Mapped[int | None] = mapped_column(Integer, nullable=True)
    quota_period: Mapped[str | None] = mapped_column(String(20), nullable=True)
    quota_used: Mapped[int] = mapped_column(Integer, nullable=False, default=0, server_default="0")
    quota_reset_at: Mapped[dt.datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)

    # Partie 9.2.2 -- real, additive: a real, future timestamp a real
    # Celery beat task (`api/tasks/api_key_maintenance.py`) checks
    # against to execute a real, planned rotation automatically.
    scheduled_rotation_at: Mapped[dt.datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)

    __table_args__ = (UniqueConstraint("organization_id", "name", name="uq_organization_api_keys_org_id_name"),)


class KeyRotationHistory(Base):
    """Partie 9.2.2 -- real, append-only audit trail of every real
    rotation. `rotated_from`/`rotated_to` are real, nullable FKs to
    the SAME real table above -- nullable because a rotated-away-from
    key is often hard-deleted later, but its own real rotation
    history row must survive that (`ON DELETE SET NULL`, never
    CASCADE, unlike a real revocation)."""

    __tablename__ = "key_rotation_history"

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    key_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("organization_api_keys.id", ondelete="CASCADE"), nullable=False, index=True)
    rotated_from: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("organization_api_keys.id", ondelete="SET NULL"), nullable=True)
    rotated_to: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("organization_api_keys.id", ondelete="SET NULL"), nullable=True)
    rotated_by: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("users.id", ondelete="SET NULL"), nullable=True)
    rotated_at: Mapped[dt.datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    reason: Mapped[str | None] = mapped_column(Text, nullable=True)
    metadata_json: Mapped[dict | None] = mapped_column(JSON, nullable=True)
