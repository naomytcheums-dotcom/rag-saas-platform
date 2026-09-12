"""
Partie 1.3.10 -- per-organization branding (logo, favicon, colors, font,
custom name, custom CSS). One row per organization (created alongside
it, see api/security/organizations.py's create_organization_with_owner,
same "never without each other" reasoning as Partie 1.3.6's quotas).

Unlike Partie 1.3.9's organization_settings (an open-ended JSON blob of
overrides merged with defaults at read time), this is a small, fixed
set of real, typed columns with real defaults on the row itself -- the
same shape as OrganizationQuota, not OrganizationSettings.

Extended in Partie 19 (white-label) with 6 more real, typed columns
(company_email/support_email/email_sender_name/email_sender_email/
custom_js/is_active) -- still this table, deliberately: Partie 19's own
spec asked for a brand-new `WhiteLabelConfig` model, but every single
field it named beyond these 6 (logo_url, favicon_url, colors, name,
custom_css, hide_branding, domain/domain_verified) already existed here
or on CustomDomain (Partie 1.4.1). A second table would have meant two
independent, potentially-disagreeing sources of truth for the exact
same data -- the one mistake api/security/white_label.py's own
docstring already documents rejecting once, for the exact same reason.
"""

import datetime as dt
import uuid

from sqlalchemy import Boolean, DateTime, ForeignKey, String, Text, UniqueConstraint, func
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
    # Partie 1.4.6 -- when true, a consuming frontend should hide this
    # platform's own name/logo/legal mentions and show ONLY this
    # organization's own brand_name/logo_url/favicon_url instead. Lives
    # here, not on organization_settings (Partie 1.3.9's JSON overrides
    # blob) -- see api/security/white_label.py's own docstring for why
    # duplicating the same boolean as an independent key in a second
    # table was deliberately rejected rather than silently done because
    # the original spec asked for both.
    hide_platform_branding: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    # Partie 19 -- white-label extension. company_email/support_email are
    # contact-info display fields (shown to the org's own end users, e.g.
    # in a footer); email_sender_name/email_sender_email are a DIFFERENT,
    # narrower thing -- the reply-to identity shown on outbound emails,
    # independent of Partie 1.4.5's custom-domain sending (which sends
    # FROM the verified domain itself; this is just the display name/
    # reply-to address, real regardless of whether a custom domain is
    # even configured).
    company_email: Mapped[str | None] = mapped_column(String(254), nullable=True)
    support_email: Mapped[str | None] = mapped_column(String(254), nullable=True)
    email_sender_name: Mapped[str | None] = mapped_column(String(200), nullable=True)
    email_sender_email: Mapped[str | None] = mapped_column(String(254), nullable=True)
    custom_js: Mapped[str | None] = mapped_column(Text, nullable=True)
    # A real kill switch, distinct from hide_platform_branding (which
    # only hides THIS platform's own identity): is_active=False means
    # "ignore every custom field on this row, render pure platform
    # defaults" -- e.g. an org that configured white-label then
    # downgraded off the plan that includes it, without losing its
    # saved configuration.
    is_active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    created_at: Mapped[dt.datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[dt.datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())

    __table_args__ = (
        UniqueConstraint("organization_id", name="uq_organization_branding_organization_id"),
    )
