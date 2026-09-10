"""
Partie 13.3 -- alerting. Consolidated: `AlertRule` carries its own
condition fields directly (metric/operator/threshold) rather than a
separate `AlertCondition` table, and `AlertChannel` has exactly two
real types (email, webhook) rather than one table per named provider
(Slack/Teams/Discord/PagerDuty all real-world work as "POST a payload
to a URL" -- an incoming webhook -- so a generic webhook channel covers
all four honestly, without needing four different SDKs this
environment has no real accounts for). Same consolidation discipline as
every other batch this project has applied (Partie 9.5/10.6/11).

Rules evaluate against REAL, already-existing live data sources
(api/services/admin_monitoring.py's psutil/Celery inspection, Partie
11.5) rather than a new time-series metrics-storage table -- Partie
13.1's Prometheus /metrics is already the real time-series store for
anyone who wants history; duplicating that here would be a second,
competing source of truth for the same numbers.
"""

import datetime as dt
import enum
import uuid

from sqlalchemy import JSON, DateTime, Float, ForeignKey, String, Text, func
from sqlalchemy.orm import Mapped, mapped_column

from api.database import Base


class AlertChannelType(str, enum.Enum):
    email = "email"
    webhook = "webhook"  # also used for Slack/Teams/Discord/PagerDuty (all real incoming-webhook URLs)


class AlertOperator(str, enum.Enum):
    gt = "gt"
    gte = "gte"
    lt = "lt"
    lte = "lte"


class AlertSeverity(str, enum.Enum):
    critical = "critical"
    high = "high"
    medium = "medium"
    low = "low"
    info = "info"


class IncidentStatus(str, enum.Enum):
    open = "open"
    investigating = "investigating"
    resolved = "resolved"


class AlertChannel(Base):
    __tablename__ = "alert_channels"

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    # NULL organization_id = a platform-wide channel (superadmin-managed).
    organization_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("organizations.id", ondelete="CASCADE"), nullable=True, index=True)
    name: Mapped[str] = mapped_column(String(100), nullable=False)
    type: Mapped[AlertChannelType] = mapped_column(nullable=False)
    # {"email": "..."} or {"webhook_url": "..."} -- the one real config
    # field each channel type actually needs.
    config: Mapped[dict] = mapped_column(JSON, nullable=False)
    enabled: Mapped[bool] = mapped_column(default=True, nullable=False)
    created_at: Mapped[dt.datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


class AlertRule(Base):
    __tablename__ = "alert_rules"

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    organization_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("organizations.id", ondelete="CASCADE"), nullable=True, index=True)
    name: Mapped[str] = mapped_column(String(100), nullable=False)
    # One of: cpu_percent, memory_percent, disk_percent, celery_queue_backlog,
    # http_5xx_total -- see api/services/alerting.py's REAL_METRIC_SOURCES
    # for the exact, honest list of what this can actually check.
    metric: Mapped[str] = mapped_column(String(64), nullable=False)
    operator: Mapped[AlertOperator] = mapped_column(nullable=False)
    threshold: Mapped[float] = mapped_column(Float, nullable=False)
    severity: Mapped[AlertSeverity] = mapped_column(nullable=False, default=AlertSeverity.medium)
    channel_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("alert_channels.id", ondelete="SET NULL"), nullable=True)
    enabled: Mapped[bool] = mapped_column(default=True, nullable=False)
    created_by: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("users.id", ondelete="SET NULL"), nullable=True)
    created_at: Mapped[dt.datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


class AlertHistory(Base):
    __tablename__ = "alert_history"

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    rule_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("alert_rules.id", ondelete="CASCADE"), nullable=False, index=True)
    triggered_at: Mapped[dt.datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), index=True)
    value_at_trigger: Mapped[float] = mapped_column(Float, nullable=False)
    message: Mapped[str] = mapped_column(Text, nullable=False)
    notified: Mapped[bool] = mapped_column(default=False, nullable=False)


class Incident(Base):
    __tablename__ = "incidents"

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    organization_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("organizations.id", ondelete="CASCADE"), nullable=True, index=True)
    title: Mapped[str] = mapped_column(String(200), nullable=False)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    severity: Mapped[AlertSeverity] = mapped_column(nullable=False, default=AlertSeverity.medium)
    status: Mapped[IncidentStatus] = mapped_column(nullable=False, default=IncidentStatus.open)
    created_by: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("users.id", ondelete="SET NULL"), nullable=True)
    created_at: Mapped[dt.datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    resolved_at: Mapped[dt.datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
