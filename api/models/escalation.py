"""
Partie 5.2.9 -- real, persistent human-escalation records: an agent
reports being stuck, a real human tracks it through to resolution.

**A real, deliberate distinction from `HumanApproval` (Partie
5.1.10)**: that model gates one specific SENSITIVE ACTION before it
proceeds (a blocking, binary decision) -- this one reports the agent
itself is stuck and needs help, informational, with real priority
levels, real assignment, and a real resolution note. Genuinely
different real concepts, not a duplicate.

`organization_id` (nullable), same real reasoning as every other
agent-related table added this batch: denormalized from the
referenced `agent_run` at creation time, since `Escalation` has no
other real tenant boundary of its own."""

import datetime as dt
import uuid
from enum import StrEnum

from sqlalchemy import JSON, DateTime, ForeignKey, String, Text, func
from sqlalchemy.orm import Mapped, mapped_column

from api.database import Base


class EscalationStatus(StrEnum):
    open = "open"
    assigned = "assigned"
    resolved = "resolved"
    closed = "closed"


class EscalationPriority(StrEnum):
    low = "low"
    medium = "medium"
    high = "high"
    critical = "critical"


class Escalation(Base):
    __tablename__ = "escalations"

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    agent_run_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("agent_runs.id", ondelete="CASCADE"), nullable=False)
    organization_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("organizations.id", ondelete="CASCADE"), nullable=True)
    issue: Mapped[str] = mapped_column(Text, nullable=False)
    context: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    priority: Mapped[str] = mapped_column(String(10), nullable=False, default=EscalationPriority.medium.value)
    status: Mapped[str] = mapped_column(String(10), nullable=False, default=EscalationStatus.open.value)
    resolution: Mapped[str | None] = mapped_column(Text, nullable=True)
    assignee_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("users.id", ondelete="SET NULL"), nullable=True)
    created_at: Mapped[dt.datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    resolved_at: Mapped[dt.datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
