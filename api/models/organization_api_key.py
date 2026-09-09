"""
Partie 9.1 -- real, revocable, ORGANIZATION-scoped API keys for the
public `/v1/*` API.

**Incohérence réelle corrigée -- pas une copie forcée de `AgentAPIKey`**:
5.3.10's own `AgentAPIKey` (`api/models/agent_api_key.py`) is scoped to
ONE real agent, for one real endpoint (`POST /api/agents/run`). Partie
9.1's own 9 endpoints span an entire organization (any agent, document
uploads, knowledge bases, search, usage, embeddings) -- a genuinely
different real scope, not the same real entity reused. This is a new,
separate model, reusing the exact same real hash/generation
DISCIPLINE as `agent_api_keys.py` (SHA-256 hash, one-time plaintext
reveal), never the same real row shape."""

import datetime as dt
import uuid

from sqlalchemy import JSON, DateTime, ForeignKey, String, UniqueConstraint, func
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
    created_by: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("users.id", ondelete="SET NULL"), nullable=True)
    created_at: Mapped[dt.datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    revoked_at: Mapped[dt.datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)

    __table_args__ = (UniqueConstraint("organization_id", "name", name="uq_organization_api_keys_org_id_name"),)
