"""Phase 5, Étape 23 -- DB-backed notification templates.

Real, additive scope: the code-defined `TEMPLATES` dict in
`api/services/notification_templates.py` stays as the real, always-available
fallback (so a fresh install with an empty DB still sends real,
correct notifications). This table is the real, admin-editable override
layer: an org admin can customize a template's wording per organization
without a redeploy.

Lookup order at render time:
1. Organization-specific row (organization_id = the org, type = the type)
2. Global row (organization_id IS NULL, type = the type)
3. Code-defined `TEMPLATES[type]` (always present)
"""

import datetime as dt
import uuid

from sqlalchemy import JSON, Boolean, DateTime, ForeignKey, String, Text, UniqueConstraint, func
from sqlalchemy.orm import Mapped, mapped_column

from api.database import Base


class NotificationTemplate(Base):
    __tablename__ = "notification_templates"

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    # NULL = global template (applies to every organization that hasn't
    # overridden it). Non-NULL = that specific organization's override.
    organization_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("organizations.id", ondelete="CASCADE"),
        nullable=True,
        index=True,
    )
    notification_type: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
    title: Mapped[str] = mapped_column(String(500), nullable=False)
    body: Mapped[str] = mapped_column(Text, nullable=False)
    email_subject: Mapped[str | None] = mapped_column(String(500), nullable=True)
    is_active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    created_by: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("users.id", ondelete="SET NULL"),
        nullable=True,
    )
    created_at: Mapped[dt.datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[dt.datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())

    __table_args__ = (
        # One row per (organization, type) pair. NULL organization_id
        # (the global default) is a separate, distinct row.
        UniqueConstraint(
            "organization_id", "notification_type",
            name="uq_notification_template_org_type",
        ),
    )
