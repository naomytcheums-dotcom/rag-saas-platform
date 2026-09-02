"""
Partie 1.3.3 -- Teams: a logical grouping of users WITHIN an organization
(e.g. "Support", "Engineering"), distinct from the organization role
hierarchy (Etape 1.2.2-1.2.6). A user's org role (Member, Manager, ...)
governs what they can do across the whole organization; team membership
is orthogonal -- who they work with day to day. A user can belong to
several teams at once.

`TeamMember.role` is its OWN small axis (admin/member), scoped to ONE
team, not the organization -- a plain org Member can be a team's admin
(managing who's on that team) without their org role changing at all.
See api/security/teams.py for how the two axes actually combine at
permission-check time.
"""

import datetime as dt
import enum
import uuid

from sqlalchemy import DateTime, Enum, ForeignKey, String, Text, UniqueConstraint, func
from sqlalchemy.orm import Mapped, mapped_column

from api.database import Base


class TeamRole(str, enum.Enum):
    """Same "native Postgres enum, fixed small set" choice as
    api/models/organization.py's OrganizationRole -- team-scoped
    admin/member is not expected to grow the way AuditAction does."""

    admin = "admin"
    member = "member"


class Team(Base):
    __tablename__ = "teams"

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    organization_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("organizations.id", ondelete="CASCADE"), nullable=False, index=True
    )
    name: Mapped[str] = mapped_column(String(200), nullable=False)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    # SET NULL, not CASCADE -- a team outlives the account that created
    # it, same reasoning as api/models/workspace.py's created_by.
    created_by: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("users.id", ondelete="SET NULL"), nullable=True)
    created_at: Mapped[dt.datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[dt.datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )


class TeamMember(Base):
    __tablename__ = "team_members"

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    team_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("teams.id", ondelete="CASCADE"), nullable=False, index=True)
    user_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True)
    role: Mapped[TeamRole] = mapped_column(Enum(TeamRole), default=TeamRole.member, nullable=False)
    joined_at: Mapped[dt.datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())

    __table_args__ = (
        UniqueConstraint("team_id", "user_id", name="uq_team_members_team_user"),
    )
