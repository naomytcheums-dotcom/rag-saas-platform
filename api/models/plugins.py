"""
Partie 16 (ter) -- plugin marketplace. Numbering collision, same
pattern as every prior one: DeepSeek's own "Partie 16" was already used
this session for the 4 sales models (docs/sales/*.md, migration
0094_partie_16_sales_models.py) -- documented as "(ter)" since "(bis)"
is already taken by that batch. Extended in a later pass (real
versioning via `PluginVersion`, real sandboxed execution logged in
`PluginExecution`) -- see docs/marketplace/PARTIE_16_TER_MARKETPLACE.md
for the full write-up of what changed and why.

`Plugin` -- one real row per published plugin: the identity
(name/slug/description/category/organization_id) plus its CURRENT
version's content (manifest/version/code_key), kept on this row (not
moved into `PluginVersion` alone) so every already-built and
live-verified read path (marketplace listing, install, the dry-run
test) keeps working unchanged against "the current version" without a
join. `PluginVersion` is an additive, append-only history: one real row
written on every publish/republish, holding that exact version's
manifest/code snapshot -- genuinely new value (a real changelog/
rollback record), not a duplicate of what Plugin already tracks.

`PluginInstallation` -- one real row per (plugin, installing
organization) (this is the same real concept the spec calls
"PluginInstall" -- kept under its existing, already-migrated,
already-tested name rather than renamed for a naming preference alone).
`PluginReview` -- one real row per (plugin, reviewing user), upserted
on re-review. `PluginExecution` -- one real row per sandboxed run (see
api/security/plugin_sandbox.py), whether triggered manually via
`POST .../execute` or by a real platform hook.

Deliberately NOT built as separate tables (reusing what already exists,
avoiding duplicating data): `PluginCategory` is a fixed enum + a
`category` column on `Plugin` (same static-catalog reasoning as
`PluginStatus` and `api/security/permission_catalog.py` -- nothing
needs an admin-created 9th category), and `PluginPermission` stays
inside `manifest["permissions"]` (already validated against the real,
fixed `ALLOWED_PLUGIN_PERMISSIONS` whitelist in plugin_manifest.py) --
a separate junction table would only duplicate that same JSON list.
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


class PluginCategory(str, enum.Enum):
    analytics = "analytics"
    automation = "automation"
    communication = "communication"
    data = "data"
    integration = "integration"
    productivity = "productivity"
    security = "security"
    other = "other"


class PluginExecutionStatus(str, enum.Enum):
    success = "success"
    error = "error"
    timeout = "timeout"


class Plugin(Base):
    __tablename__ = "plugins"

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    organization_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("organizations.id", ondelete="CASCADE"), nullable=False, index=True)
    name: Mapped[str] = mapped_column(String(200), nullable=False)
    slug: Mapped[str] = mapped_column(String(100), nullable=False, unique=True)
    description: Mapped[str] = mapped_column(Text, nullable=False)
    category: Mapped[PluginCategory] = mapped_column(nullable=False, default=PluginCategory.other)
    # The CURRENT version's real, validated manifest.json content (see
    # this module's own top docstring on why this stays here rather
    # than only in PluginVersion).
    manifest: Mapped[dict] = mapped_column(JSON, nullable=False)
    version: Mapped[str] = mapped_column(String(50), nullable=False)
    # The real S3 key of this plugin's CURRENT uploaded code
    # (api/services/plugins.py's own upload_plugin_code).
    code_key: Mapped[str] = mapped_column(String(500), nullable=False)
    code_size_bytes: Mapped[int] = mapped_column(Integer, nullable=False)
    status: Mapped[PluginStatus] = mapped_column(nullable=False, default=PluginStatus.pending)
    rejection_reason: Mapped[str | None] = mapped_column(Text, nullable=True)
    # Real, live-maintained counter (incremented/decremented directly by
    # install_plugin/uninstall_plugin for immediate accuracy), also
    # periodically reconciled from a real COUNT query by
    # api/tasks/plugins.py's own update_plugin_stats -- same
    # direct-update-plus-periodic-reconciliation pattern this project
    # already uses elsewhere (e.g. billing usage). Drives marketplace
    # "sort by popularity".
    install_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    created_by: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("users.id", ondelete="SET NULL"), nullable=True)
    created_at: Mapped[dt.datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[dt.datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())


class PluginVersion(Base):
    """A real, append-only history row written on every publish/
    republish -- api/services/plugins.py's own publish_plugin/
    republish_plugin write one of these alongside updating `Plugin`
    itself. Never updated after creation (a real changelog/rollback
    record), unlike `Plugin`'s own mutable "current version" columns."""

    __tablename__ = "plugin_versions"
    __table_args__ = (UniqueConstraint("plugin_id", "version", name="uq_plugin_version"),)

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    plugin_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("plugins.id", ondelete="CASCADE"), nullable=False, index=True)
    version: Mapped[str] = mapped_column(String(50), nullable=False)
    manifest: Mapped[dict] = mapped_column(JSON, nullable=False)
    code_key: Mapped[str] = mapped_column(String(500), nullable=False)
    code_size_bytes: Mapped[int] = mapped_column(Integer, nullable=False)
    changelog: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_by: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("users.id", ondelete="SET NULL"), nullable=True)
    created_at: Mapped[dt.datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


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


class PluginExecution(Base):
    """One real row per sandboxed run (api/security/plugin_sandbox.py's
    own run_plugin_sandboxed), whether triggered manually via
    `POST .../execute` or by a real platform hook via
    api/services/plugin_hooks.py's own trigger_hook. `hook` is null for
    a manual/API-triggered execution."""

    __tablename__ = "plugin_executions"

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    plugin_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("plugins.id", ondelete="CASCADE"), nullable=False, index=True)
    organization_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("organizations.id", ondelete="CASCADE"), nullable=False, index=True)
    installation_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("plugin_installations.id", ondelete="SET NULL"), nullable=True)
    hook: Mapped[str | None] = mapped_column(String(50), nullable=True)
    status: Mapped[PluginExecutionStatus] = mapped_column(nullable=False)
    input_payload: Mapped[dict] = mapped_column(JSON, nullable=False)
    output_payload: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    error_message: Mapped[str | None] = mapped_column(Text, nullable=True)
    duration_ms: Mapped[int | None] = mapped_column(Integer, nullable=True)
    created_by: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("users.id", ondelete="SET NULL"), nullable=True)
    created_at: Mapped[dt.datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), index=True)
