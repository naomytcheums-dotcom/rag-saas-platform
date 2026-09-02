"""
Partie 1.3.10 -- per-organization branding (logo, favicon, colors, font,
custom name, custom CSS). One row per organization (created alongside
it, see api/security/organizations.py's create_organization_with_owner,
same "never without each other" reasoning as Partie 1.3.6's quotas).

Unlike Partie 1.3.9's organization_settings (an open-ended JSON blob of
overrides merged with defaults at read time), this is a small, fixed
set of real, typed columns with real defaults on the row itself -- the
same shape as OrganizationQuota, not OrganizationSettings. Branding is
a closed set of 8 fields this step names explicitly, not something
expected to grow arbitrarily the way configuration keys might.
"""

import datetime as dt
import uuid

from sqlalchemy import DateTime, ForeignKey, String, Text, UniqueConstraint, func
from sqlalchemy.orm import Mapped, mapped_column

from api.database import Base


class OrganizationBranding(Base):
    __tablename__ = "organization_branding"

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    organization_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("organizations.id", ondelete="CASCADE"), nullable=False)
    # Nullable: no logo/favicon uploaded yet is a real, valid, default
    # state -- not a missing value to fall back from the way a color
    # falls back to its default.
    logo_url: Mapped[str | None] = mapped_column(Text, nullable=True)
    favicon_url: Mapped[str | None] = mapped_column(Text, nullable=True)
    primary_color: Mapped[str] = mapped_column(String(7), nullable=False, default="#2563eb")
    secondary_color: Mapped[str] = mapped_column(String(7), nullable=False, default="#1e293b")
    accent_color: Mapped[str] = mapped_column(String(7), nullable=False, default="#f59e0b")
    font_family: Mapped[str] = mapped_column(String(100), nullable=False, default="Inter")
    brand_name: Mapped[str | None] = mapped_column(String(200), nullable=True)
    custom_css: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[dt.datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[dt.datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())

    __table_args__ = (
        UniqueConstraint("organization_id", name="uq_organization_branding_organization_id"),
    )
