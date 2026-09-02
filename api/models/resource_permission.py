"""
Etape 1.2.8 -- per-resource-instance, per-user permission overrides
("Viewer X can also `update` this ONE document/workspace") on top of the
organization role hierarchy (Etape 1.2.2-1.2.6). `resource_type` is
plain String, not a native Postgres enum -- same reasoning as
api/models/audit_log.py's AuditAction: new resource types (document,
conversation, agent, knowledge_base -- Parties 2/3, not built yet) must
never need a migration just to become grantable data, even though
today's code only actually ENFORCES grants for "workspace" (see
api/security/resource_permissions.py's SUPPORTED_RESOURCE_ACTIONS).

`resource_id` has no foreign key -- it can't: it points at a different
table depending on `resource_type` (a polymorphic reference), which
relational FKs can't express without a table-per-type join scheme this
step doesn't need. A row whose resource_id no longer exists (e.g. the
workspace it named was deleted) becomes silently unreachable rather than
erroring -- see api/security/resource_permissions.py's own docstring for
why this is an accepted, documented limitation rather than a bug to fix
here.
"""

import datetime as dt
import uuid

from sqlalchemy import DateTime, ForeignKey, Index, String, UniqueConstraint, func
from sqlalchemy.orm import Mapped, mapped_column

from api.database import Base


class ResourcePermission(Base):
    __tablename__ = "resource_permissions"

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    organization_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("organizations.id", ondelete="CASCADE"), nullable=False, index=True
    )
    resource_type: Mapped[str] = mapped_column(String(50), nullable=False)
    resource_id: Mapped[uuid.UUID] = mapped_column(nullable=False)
    user_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), nullable=False)
    action: Mapped[str] = mapped_column(String(50), nullable=False)
    # SET NULL, not CASCADE -- deleting the grantor's account should not
    # delete the permission they granted (same reasoning as
    # OrganizationMember.invited_by), just lose attribution.
    granted_by: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("users.id", ondelete="SET NULL"), nullable=True)
    granted_at: Mapped[dt.datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    expires_at: Mapped[dt.datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)

    __table_args__ = (
        UniqueConstraint(
            "organization_id", "resource_type", "resource_id", "user_id", "action",
            name="uq_resource_permissions_org_resource_user_action",
        ),
        # Serves get_user_resource_permissions(user_id) with no
        # resource_type/id filter -- the unique constraint above already
        # covers every other lookup shape (it's a composite index
        # leading with organization_id/resource_type/resource_id/user_id,
        # exactly what check_resource_permission's WHERE clause needs).
        Index("ix_resource_permissions_user_id", "user_id"),
        # Serves "list every permission granted on this resource"
        # (GET /resources/{type}/{id}/permissions) without needing a
        # specific user_id.
        Index("ix_resource_permissions_resource", "resource_type", "resource_id"),
    )
