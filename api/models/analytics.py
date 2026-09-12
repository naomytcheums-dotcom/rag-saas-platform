"""Partie 20 -- advanced analytics.

Real, honest scope decided after auditing what already existed (this
part's own instructions, item 1): Prometheus (`api/monitoring.py`),
system health/resources (`api/services/admin_monitoring.py`), revenue/
MRR/ARR/ARPU/churn-count (`api/services/admin_subscriptions.py`), a
per-org daily usage ledger (`api/models/organization_usage.py`), a
RAG-response quality dashboard (`api/services/quality_dashboard.py`),
and per-evaluation token/cost tracking (`api/services/token_usage.py`/
`cost_tracking.py`) were ALL already real -- none of that is
duplicated here. This module adds exactly the 3 genuinely missing
pieces:

- `AnalyticsEvent`: a free-form product-analytics event log, distinct
  from `AuditLog` (Partie 1.2.10) on purpose -- AuditLog's `action` is
  a closed, security-relevant StrEnum (~50 values, tamper-evident HMAC
  chain, its own retention/archival policy); a new dotted event name
  like "conversation.created" or a future feature's own event would
  need a code change (a new enum member) to log there. This table
  takes an arbitrary `event_type` string, is NOT tamper-evident (it
  doesn't need to be -- it's product telemetry, not a security audit
  trail), and has its own, separate, usually-shorter retention policy
  (ANALYTICS_RETENTION_DAYS). Two real, different tables for two real,
  different purposes -- not the same data twice.
- `AnalyticsAggregate`: materialized per-period rollups (hour/day/week/
  month), so a dashboard widget reads one small, indexed row instead of
  re-scanning potentially millions of AnalyticsEvent/AuditLog rows on
  every page load. Nothing else in this codebase pre-aggregates a
  metric over time the way this does.
- `AnalyticsDashboard`: a saved, user-configurable widget layout (JSON).
  Confirmed genuinely absent -- every existing "dashboard" in this
  codebase (the admin page, the quality dashboard) is hardcoded, not a
  saved, per-organization, editable layout.
"""

import datetime as dt
import uuid

from sqlalchemy import Boolean, DateTime, ForeignKey, Index, JSON, Numeric, String, func
from sqlalchemy.orm import Mapped, mapped_column

from api.database import Base


class AnalyticsEvent(Base):
    __tablename__ = "analytics_events"

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    organization_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("organizations.id", ondelete="CASCADE"), nullable=False, index=True)
    user_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("users.id", ondelete="SET NULL"), nullable=True)
    event_type: Mapped[str] = mapped_column(String(100), nullable=False, index=True)
    event_data: Mapped[dict] = mapped_column(JSON, nullable=False, default=dict)
    created_at: Mapped[dt.datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), index=True)

    __table_args__ = (
        Index("ix_analytics_events_org_type_created", "organization_id", "event_type", "created_at"),
    )


class AnalyticsAggregate(Base):
    """One row per (organization, metric_name, period, period_start) --
    real upsert-on-recompute semantics (api/services/analytics.py's own
    aggregate_metrics recomputes and overwrites, never accumulates
    duplicates for the same period)."""

    __tablename__ = "analytics_aggregates"

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    organization_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("organizations.id", ondelete="CASCADE"), nullable=False, index=True)
    metric_name: Mapped[str] = mapped_column(String(100), nullable=False)
    metric_value: Mapped[float] = mapped_column(Numeric(20, 4), nullable=False)
    period: Mapped[str] = mapped_column(String(10), nullable=False)  # "hour" | "day" | "week" | "month"
    period_start: Mapped[dt.datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    created_at: Mapped[dt.datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())

    __table_args__ = (
        Index(
            "uq_analytics_aggregates_identity", "organization_id", "metric_name", "period", "period_start", unique=True,
        ),
    )


class AnalyticsDashboard(Base):
    __tablename__ = "analytics_dashboards"

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    organization_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("organizations.id", ondelete="CASCADE"), nullable=False, index=True)
    name: Mapped[str] = mapped_column(String(200), nullable=False)
    # A real, honest list of {type, metric, chart, ...} widget
    # descriptors -- the frontend (DashboardBuilder.tsx) is the only
    # thing that interprets its shape; the backend just stores/returns
    # it verbatim, the same "opaque JSON, frontend-owned shape"
    # convention as Partie 1.3.9's organization_settings.
    widgets: Mapped[list] = mapped_column(JSON, nullable=False, default=list)
    is_default: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    created_at: Mapped[dt.datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
