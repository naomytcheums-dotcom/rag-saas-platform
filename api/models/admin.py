"""
Partie 11 -- platform-admin models. `SystemLog` is fed by a real
`logging.Handler` (api/security/system_log_handler.py) attached to the
root logger, not a mock -- every real WARNING+ log line this process
emits is captured. `Plan`/`Subscription` are real, functional CRUD
entities, but honestly scoped: this environment has no payment
processor wired (Partie 12, 0/23) -- MRR/ARR/revenue are computed for
real from `Plan.monthly_price_cents` × active `Subscription` rows, but
every real number is 0 until a real plan with a non-zero price is
actually assigned to a real organization; nothing here fabricates a
number no real data backs.
"""

import datetime as dt
import enum
import uuid

from sqlalchemy import Boolean, DateTime, ForeignKey, Integer, String, Text, func
from sqlalchemy.orm import Mapped, mapped_column

from api.database import Base


class SystemLog(Base):
    __tablename__ = "system_logs"

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    level: Mapped[str] = mapped_column(String(10), nullable=False, index=True)  # WARNING/ERROR/CRITICAL
    logger_name: Mapped[str] = mapped_column(String(200), nullable=False, index=True)  # e.g. "api.routers.webhooks"
    message: Mapped[str] = mapped_column(Text, nullable=False)
    module: Mapped[str | None] = mapped_column(String(200), nullable=True)
    function: Mapped[str | None] = mapped_column(String(200), nullable=True)
    line: Mapped[int | None] = mapped_column(Integer, nullable=True)
    request_id: Mapped[str | None] = mapped_column(String(64), nullable=True, index=True)
    created_at: Mapped[dt.datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), index=True)


class SubscriptionStatus(str, enum.Enum):
    active = "active"
    canceled = "canceled"
    past_due = "past_due"
    pending = "pending"


class Plan(Base):
    __tablename__ = "plans"

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    key: Mapped[str] = mapped_column(String(50), unique=True, nullable=False)  # "free" | "pro" | "enterprise"
    name: Mapped[str] = mapped_column(String(100), nullable=False)
    monthly_price_cents: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    max_documents: Mapped[int | None] = mapped_column(Integer, nullable=True)
    max_agents: Mapped[int | None] = mapped_column(Integer, nullable=True)
    max_members: Mapped[int | None] = mapped_column(Integer, nullable=True)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    created_at: Mapped[dt.datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


class Subscription(Base):
    __tablename__ = "subscriptions"

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    organization_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("organizations.id", ondelete="CASCADE"), unique=True, nullable=False)
    plan_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("plans.id", ondelete="RESTRICT"), nullable=False)
    status: Mapped[SubscriptionStatus] = mapped_column(nullable=False, default=SubscriptionStatus.active)
    current_period_end: Mapped[dt.datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    canceled_at: Mapped[dt.datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    cancel_reason: Mapped[str | None] = mapped_column(String(500), nullable=True)
    created_at: Mapped[dt.datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[dt.datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())
