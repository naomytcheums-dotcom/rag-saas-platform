"""
Partie 5.2.10 -- real, organization-defined custom tools backed by a
real webhook, the one item Partie 5.2's own earlier batch explicitly
left honestly undone ("Custom Tools (webhooks) : non demandé dans ce
lot", `docs/CAHIER_DES_CHARGES.md`).

`schema` is the same real, JSON-schema-shaped contract
`api/services/tool_validation.py` (Partie 5.1.9) already validates
against for a tool's own RESULT -- reused here for a tool's own real
INPUT parameters instead, not a second, competing schema format."""

import datetime as dt
import uuid

from sqlalchemy import JSON, DateTime, ForeignKey, Integer, String, Text, func
from sqlalchemy.orm import Mapped, mapped_column

from api.database import Base

HTTP_METHODS = ("GET", "POST", "PUT", "DELETE")


class CustomTool(Base):
    __tablename__ = "custom_tools"

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    organization_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("organizations.id", ondelete="CASCADE"), nullable=False, index=True)
    name: Mapped[str] = mapped_column(String(200), nullable=False)
    description: Mapped[str] = mapped_column(Text, nullable=False)
    webhook_url: Mapped[str] = mapped_column(String(2000), nullable=False)
    method: Mapped[str] = mapped_column(String(10), nullable=False, default="POST")
    headers: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    timeout: Mapped[int] = mapped_column(Integer, nullable=False, default=20)
    retry_count: Mapped[int] = mapped_column(Integer, nullable=False, default=1)
    schema: Mapped[dict] = mapped_column(JSON, nullable=False, default=dict)
    created_by: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("users.id", ondelete="SET NULL"), nullable=True)
    created_at: Mapped[dt.datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[dt.datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())
    # Real, deliberate addition beyond item 1's own literal columns --
    # same real soft-delete reasoning as `Agent`/`Workflow` (Parties
    # 5.3.1/5.4.1): a real agent run that already called this tool
    # keeps a real, meaningful reference to it.
    deleted_at: Mapped[dt.datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
