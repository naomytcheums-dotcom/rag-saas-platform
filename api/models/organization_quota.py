"""
Partie 1.3.6 -- per-organization resource limits. One row per
organization (created alongside it, see
api/security/organizations.py's create_organization_with_owner),
holding the 10 configurable limits this step's spec names.

Deliberately holds LIMITS only, never usage counters: for the three
resource types this codebase can actually count today (users,
workspaces, teams), usage is always computed live from the real table
(`SELECT COUNT(*) FROM organization_members WHERE organization_id = ...`,
etc. -- see api/security/quotas.py) rather than a separately
incremented column. A live count can never drift from reality; a
maintained counter can (a missed decrement on delete, a bug in the
increment call site) -- see that module's own docstring for the seven
remaining dimensions (documents, storage, requests, api_calls, agents,
KB size) that have no real table yet to count against at all.
"""

import datetime as dt
import uuid

from sqlalchemy import ForeignKey, Integer, DateTime, UniqueConstraint, func
from sqlalchemy.orm import Mapped, mapped_column

from api.database import Base


class OrganizationQuota(Base):
    __tablename__ = "organization_quotas"

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    organization_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("organizations.id", ondelete="CASCADE"), nullable=False
    )
    max_users: Mapped[int] = mapped_column(Integer, nullable=False)
    max_workspaces: Mapped[int] = mapped_column(Integer, nullable=False)
    max_teams: Mapped[int] = mapped_column(Integer, nullable=False)
    max_documents: Mapped[int] = mapped_column(Integer, nullable=False)
    max_storage_mb: Mapped[int] = mapped_column(Integer, nullable=False)
    max_requests_per_month: Mapped[int] = mapped_column(Integer, nullable=False)
    max_requests_per_day: Mapped[int] = mapped_column(Integer, nullable=False)
    max_api_calls: Mapped[int] = mapped_column(Integer, nullable=False)
    max_agents: Mapped[int] = mapped_column(Integer, nullable=False)
    max_kb_size_mb: Mapped[int] = mapped_column(Integer, nullable=False)
    created_at: Mapped[dt.datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[dt.datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )

    __table_args__ = (
        UniqueConstraint("organization_id", name="uq_organization_quotas_organization_id"),
    )
