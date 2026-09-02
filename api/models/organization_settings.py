"""
Partie 1.3.9 -- per-organization configuration (chunk size, embedding
model, LLM provider/model, retrieval strategy, etc.). One row per
organization (created alongside it, see
api/security/organizations.py's create_organization_with_owner, same
"never without each other" reasoning as Partie 1.3.6's quotas), holding
ONLY the settings this organization has explicitly overridden -- never
a full copy of every default. api/security/organization_settings.py's
DEFAULT_SETTINGS is the single source of truth for what an unset key
resolves to; get_org_settings() merges the two at read time. This keeps
a fresh organization's row a bare `{}` rather than a 14-key snapshot
that would silently go stale the day a new default is introduced or an
existing one changes.

`settings` uses the generic, cross-dialect sa.JSON type, not
sqlalchemy.dialects.postgresql.JSONB -- the SQLite fast suite (schema
built straight from these ORM models via Base.metadata.create_all(),
never Alembic) cannot represent JSONB at all. Same trap Identity()
sprung on password_history.sequence, and the same choice already made
for organization_usage_details.metadata_json (Partie 1.3.8) -- see that
model's own docstring.
"""

import datetime as dt
import uuid

from sqlalchemy import JSON, DateTime, ForeignKey, UniqueConstraint, func
from sqlalchemy.orm import Mapped, mapped_column

from api.database import Base


class OrganizationSettings(Base):
    __tablename__ = "organization_settings"

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    organization_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("organizations.id", ondelete="CASCADE"), nullable=False)
    # Only explicitly-overridden keys live here -- see this module's own
    # docstring for why an empty {} (every default) is the normal,
    # expected state for most organizations, not an incomplete row.
    settings: Mapped[dict] = mapped_column(JSON, nullable=False, default=dict)
    created_at: Mapped[dt.datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[dt.datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())

    __table_args__ = (
        UniqueConstraint("organization_id", name="uq_organization_settings_organization_id"),
    )
