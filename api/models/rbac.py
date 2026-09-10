"""
Partie 10.1 -- custom roles and granular permissions, layered ON TOP of
the existing fixed org-role hierarchy (api/models/organization.py's
OrganizationRole: owner/admin/manager/member/viewer). That hierarchy is
NOT replaced -- it still gates every existing endpoint unchanged. This
module adds an ADDITIVE second axis: an organization can define its own
named roles (e.g. "Support agent", "Billing viewer") and grant each one
a precise set of resource:action permissions, for the cases the fixed
5-tier hierarchy is too coarse for (e.g. someone who should read
billing but never touch security settings, a shape no combination of
owner/admin/manager/member/viewer expresses).

A user's EFFECTIVE permission set (see api/services/rbac_custom.py's
get_user_effective_permissions) is the union of every custom role
assigned to them in that organization -- there is deliberately no
"deny" permission and no per-permission override on top of a role:
composing multiple additive roles is the whole model, matching this
codebase's existing preference for simple, auditable authorization over
a general-purpose policy engine (see api/security/rbac.py's own
docstring on why the pre-existing Casbin scaffold there was deliberately
left unwired to live routes).
"""

import datetime as dt
import uuid

from sqlalchemy import DateTime, ForeignKey, String, Text, UniqueConstraint, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from api.database import Base


class PermissionGroup(Base):
    """A named grouping of permissions for display purposes only (e.g.
    "Documents", "Billing") -- purely organizational, carries no
    authorization logic of its own. Seeded once, see
    api/security/permission_catalog.py's PERMISSION_GROUPS."""

    __tablename__ = "permission_groups"

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    key: Mapped[str] = mapped_column(String(50), unique=True, nullable=False)
    label: Mapped[str] = mapped_column(String(100), nullable=False)
    sort_order: Mapped[int] = mapped_column(default=0, nullable=False)

    permissions: Mapped[list["Permission"]] = relationship(back_populates="group")


class Permission(Base):
    """One row per real `resource:action` pair -- the fixed catalog in
    api/security/permission_catalog.py (13 resources x 4 actions = 52
    rows), never admin-creatable: a permission is a capability THIS
    codebase's routers actually check for, not an arbitrary string an
    org admin could invent and expect to do anything."""

    __tablename__ = "permissions"

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    # e.g. "documents:read" -- the exact string check_permission() compares against.
    key: Mapped[str] = mapped_column(String(100), unique=True, nullable=False, index=True)
    resource: Mapped[str] = mapped_column(String(50), nullable=False, index=True)
    action: Mapped[str] = mapped_column(String(20), nullable=False)
    description: Mapped[str] = mapped_column(String(255), nullable=False)
    group_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("permission_groups.id", ondelete="SET NULL"), nullable=True)

    group: Mapped["PermissionGroup | None"] = relationship(back_populates="permissions")


class CustomRole(Base):
    """An organization-defined role, e.g. "Support agent" -- distinct
    from OrganizationRole (the fixed owner/admin/manager/member/viewer
    tier every member already has); a user can hold zero, one, or
    several CustomRoles IN ADDITION TO their one fixed OrganizationRole."""

    __tablename__ = "custom_roles"

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    organization_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("organizations.id", ondelete="CASCADE"), nullable=False, index=True)
    name: Mapped[str] = mapped_column(String(100), nullable=False)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_by: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("users.id", ondelete="SET NULL"), nullable=True)
    created_at: Mapped[dt.datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[dt.datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())

    role_permissions: Mapped[list["RolePermission"]] = relationship(back_populates="role", cascade="all, delete-orphan")
    user_assignments: Mapped[list["UserCustomRole"]] = relationship(back_populates="role", cascade="all, delete-orphan")

    __table_args__ = (
        UniqueConstraint("organization_id", "name", name="uq_custom_roles_org_name"),
    )


class RolePermission(Base):
    __tablename__ = "role_permissions"

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    role_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("custom_roles.id", ondelete="CASCADE"), nullable=False, index=True)
    permission_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("permissions.id", ondelete="CASCADE"), nullable=False, index=True)

    role: Mapped["CustomRole"] = relationship(back_populates="role_permissions")
    permission: Mapped["Permission"] = relationship()

    __table_args__ = (
        UniqueConstraint("role_id", "permission_id", name="uq_role_permissions_role_permission"),
    )


class UserCustomRole(Base):
    """A user<->CustomRole assignment, scoped to the role's own
    organization implicitly (a CustomRole belongs to exactly one org, so
    this table needs no separate organization_id column of its own)."""

    __tablename__ = "user_custom_roles"

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    user_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True)
    role_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("custom_roles.id", ondelete="CASCADE"), nullable=False, index=True)
    assigned_by: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("users.id", ondelete="SET NULL"), nullable=True)
    assigned_at: Mapped[dt.datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())

    role: Mapped["CustomRole"] = relationship(back_populates="user_assignments")

    __table_args__ = (
        UniqueConstraint("user_id", "role_id", name="uq_user_custom_roles_user_role"),
    )
