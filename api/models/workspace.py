"""
Etape 1.2.4 -- the minimal `workspaces` table needed to make the Manager
role's second capability (workspace management) real, not just a
permission check with nothing behind it. Deliberately minimal: no
knowledge-base or agent linkage yet (the original spec's "regroupe KB +
agents" is Partie 1.3.2's fuller scope, once those things exist) -- just
enough structure (an org-scoped, named container) for create/list/
rename/delete to mean something.
"""

import datetime as dt
import uuid

from sqlalchemy import DateTime, ForeignKey, String, func
from sqlalchemy.orm import Mapped, mapped_column

from api.database import Base


class Workspace(Base):
    __tablename__ = "workspaces"

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    organization_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("organizations.id", ondelete="CASCADE"), nullable=False, index=True
    )
    name: Mapped[str] = mapped_column(String(200), nullable=False)
    # Nullable, SET NULL on delete: a workspace outlives whoever created
    # it (same reasoning as api/models/enterprise_sso.py's
    # created_by_admin_id) -- it's organization property, not personal
    # property of its creator.
    created_by: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("users.id", ondelete="SET NULL"), nullable=True)
    created_at: Mapped[dt.datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[dt.datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )
