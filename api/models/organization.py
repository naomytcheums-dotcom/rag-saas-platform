"""
Etape 1.2.2 -- the first slice of Partie 1.3 (multi-tenant), built now
because 1.2.2 through 1.2.6 (organization-scoped roles) cannot exist
without an `organizations` table to scope them to. This deliberately
stays minimal: just enough structure (an org, its members, and their
role) for role-checking to work -- workspaces, invitations, quotas,
branding, and everything else in Partie 1.3/1.4 are separate, later
steps, not implied by this one.

`OrganizationMember` is an "association object," not a bare many-to-many
table: it carries real data of its own (role, who invited this member,
when they joined) that a plain `secondary=` table couldn't express.
"""

import datetime as dt
import enum
import uuid

from sqlalchemy import Boolean, DateTime, Enum, ForeignKey, Integer, String, UniqueConstraint, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from api.database import Base


class OrganizationRole(str, enum.Enum):
    """Same "native Postgres enum" choice as api/models/user.py's
    UserRole -- these 5 tiers (owner/admin/manager/member/viewer) are a
    fixed, standard SaaS-org hierarchy, not something expected to grow
    the way api/models/audit_log.py's AuditAction does."""

    owner = "owner"
    admin = "admin"
    manager = "manager"
    member = "member"
    viewer = "viewer"


class Organization(Base):
    __tablename__ = "organizations"

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    name: Mapped[str] = mapped_column(String(200), nullable=False)
    # Unique, URL-safe identifier (e.g. for a future org-scoped URL or
    # subdomain) -- generated from `name` at creation time, see
    # api/security/organizations.py's generate_unique_slug().
    slug: Mapped[str] = mapped_column(String(200), unique=True, index=True, nullable=False)
    created_at: Mapped[dt.datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[dt.datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )
    # Partie 11.2 -- a real platform-admin suspend/reactivate, distinct
    # from deletion (no grace-period/purge machinery for organizations
    # exists the way it does for User -- suspension is reversible by
    # design, a deliberately softer action).
    is_suspended: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    suspended_at: Mapped[dt.datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    suspended_reason: Mapped[str | None] = mapped_column(String(500), nullable=True)

    members: Mapped[list["OrganizationMember"]] = relationship(
        back_populates="organization", cascade="all, delete-orphan"
    )

    @property
    def owner(self) -> "User | None":
        """The User who owns this organization -- requires `members`
        (and each member's `.user`) to already be eager-loaded
        (`selectinload(Organization.members).selectinload(OrganizationMember.user)`);
        this codebase never relies on implicit lazy-loading of ORM
        relationships from an async request handler (same convention
        User.oauth_accounts/sessions already follow -- see their own
        comment), so this property is for callers that have already
        loaded the data, not a query in itself."""
        owner_membership = next((m for m in self.members if m.role == OrganizationRole.owner), None)
        return owner_membership.user if owner_membership else None


class OrganizationMember(Base):
    __tablename__ = "organization_members"

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    organization_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("organizations.id", ondelete="CASCADE"), nullable=False, index=True
    )
    user_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True)
    role: Mapped[OrganizationRole] = mapped_column(Enum(OrganizationRole), default=OrganizationRole.member, nullable=False)
    # Who invited this member -- NULL for the founding Owner (nobody
    # invited them, they created the organization) and for any account
    # added by a process other than an explicit invitation.
    invited_by: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("users.id", ondelete="SET NULL"), nullable=True)
    joined_at: Mapped[dt.datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())

    # Partie 1.3.7 -- per-member overrides on top of the role hierarchy
    # above. NULL on the three numeric limits means "no personal limit
    # set" -- see api/security/user_limits.py's own docstring for why
    # that's a THIRD state, distinct from both 0 and "inherits the org
    # quota" being a number: those two resources (documents,
    # conversations) don't exist yet, so there is nothing to inherit
    # FROM today, only a value stored for later. can_create_workspaces/
    # can_create_teams default True (unrestricted, matching today's
    # unchanged role-based behavior for whoever already has the role);
    # can_invite_members defaults False for the opposite reason -- see
    # that same module's docstring for why these three booleans are NOT
    # symmetric (two are restrictive AND-gates on top of the role check,
    # one is an additive OR-gate granting a capability role alone
    # wouldn't).
    daily_request_limit: Mapped[int | None] = mapped_column(Integer, nullable=True)
    max_documents: Mapped[int | None] = mapped_column(Integer, nullable=True)
    max_conversations: Mapped[int | None] = mapped_column(Integer, nullable=True)
    can_create_workspaces: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    can_create_teams: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    can_invite_members: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)

    organization: Mapped["Organization"] = relationship(back_populates="members")
    user: Mapped["User"] = relationship(foreign_keys=[user_id], back_populates="organization_memberships")

    __table_args__ = (
        # One membership row per (org, user) -- never two roles for the
        # same person in the same organization at once.
        UniqueConstraint("organization_id", "user_id", name="uq_organization_members_org_user"),
    )
