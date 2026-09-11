"""
Partie 16 (ter) -- plugin marketplace. Numbering collision, same
pattern as every prior one: DeepSeek's own "Partie 16" was already used
this session for the 4 sales models (docs/sales/*.md, migration
0094_partie_16_sales_models.py) -- documented as "(ter)" since "(bis)"
is already taken by that batch.

`Plugin` -- one real, versionless row per published plugin (a
re-publish overwrites `manifest`/`code_key`/`version` in place rather
than a separate PluginVersion table -- the fastest real design that
still tracks what's actually installed, not a fabricated version
history nothing reads yet). `PluginInstallation` -- one real row per
(plugin, installing organization). `PluginReview` -- one real row per
(plugin, reviewing user), upserted on re-review rather than an
unbounded review log, since a marketplace rating means "this user's
CURRENT opinion", not a append-only feed.
"""

import datetime as dt
import enum
import uuid

from sqlalchemy import JSON, Boolean, DateTime, ForeignKey, Integer, String, Text, UniqueConstraint, func
from sqlalchemy.orm import Mapped, mapped_column

from api.database import Base


class PluginStatus(str, enum.Enum):
    pending = "pending"
    approved = "approved"
    rejected = "rejected"
    suspended = "suspended"


class Plugin(Base):
    __tablename__ = "plugins"

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    organization_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("organizations.id", ondelete="CASCADE"), nullable=False, index=True)
    name: Mapped[str] = mapped_column(String(200), nullable=False)
    slug: Mapped[str] = mapped_column(String(100), nullable=False, unique=True)
    description: Mapped[str] = mapped_column(Text, nullable=False)
    # The real, validated manifest.json content (api/security/plugin_manifest.py's
    # own validate_manifest) -- permissions/entry_point/version live
    # here, not duplicated as separate columns.
    manifest: Mapped[dict] = mapped_column(JSON, nullable=False)
    version: Mapped[str] = mapped_column(String(50), nullable=False)
    # The real S3 key of this plugin's uploaded code (api/services/plugins.py's
    # own upload_plugin_code) -- one opaque blob, downloaded/scanned, never
    # executed server-side (see plugin_manifest.py's own docstring on why
    # no real sandbox exists here).
    code_key: Mapped[str] = mapped_column(String(500), nullable=False)
    code_size_bytes: Mapped[int] = mapped_column(Integer, nullable=False)
    status: Mapped[PluginStatus] = mapped_column(nullable=False, default=PluginStatus.pending)
    rejection_reason: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_by: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("users.id", ondelete="SET NULL"), nullable=True)
    created_at: Mapped[dt.datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[dt.datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())


class PluginInstallation(Base):
    __tablename__ = "plugin_installations"
    __table_args__ = (UniqueConstraint("plugin_id", "organization_id", name="uq_plugin_installation_org"),)

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    plugin_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("plugins.id", ondelete="CASCADE"), nullable=False, index=True)
    organization_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("organizations.id", ondelete="CASCADE"), nullable=False, index=True)
    enabled: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    config: Mapped[dict] = mapped_column(JSON, nullable=False, default=dict)
    installed_by: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("users.id", ondelete="SET NULL"), nullable=True)
    installed_at: Mapped[dt.datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


class PluginReview(Base):
    __tablename__ = "plugin_reviews"
    __table_args__ = (UniqueConstraint("plugin_id", "user_id", name="uq_plugin_review_user"),)

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    plugin_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("plugins.id", ondelete="CASCADE"), nullable=False, index=True)
    organization_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("organizations.id", ondelete="CASCADE"), nullable=False)
    user_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), nullable=False)
    rating: Mapped[int] = mapped_column(Integer, nullable=False)  # 1-5, enforced in api/security/plugin_manifest.py's validate_rating
    comment: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[dt.datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[dt.datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())
