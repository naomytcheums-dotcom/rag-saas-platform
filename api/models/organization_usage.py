"""
Partie 1.3.8 -- per-organization usage tracking. Two tables:

- `OrganizationUsage`: one row per (organization, calendar day, metric),
  a running daily total -- what GET /organizations/{org_id}/usage reads.
  record_usage() (api/security/usage.py) reads-then-writes this row
  rather than a dialect-specific UPSERT -- same check-then-mutate
  tolerance this codebase already accepts for
  api/security/quotas.py's check_quota/require_quota_available (see
  that module's own docstring): this is an even softer number than a
  quota, a daily total meant for human review, not a hard limit
  enforced in real time, so a narrow race under heavy concurrent writes
  to the SAME (org, day, metric) key losing at most one increment is an
  accepted tradeoff, not a bug to design out.
- `OrganizationUsageDetail`: one row PER EVENT, never aggregated, for
  traceability (who did what, when, with what free-form context). Grows
  without bound -- see api/security/usage.py's own docstring for why no
  retention/purge job exists yet (not asked for by this step's spec).

Same "only wire in what a real endpoint can produce" honesty as Partie
1.3.6 (quotas) and 1.3.7 (member limits): this step's own spec names
metrics ("requetes", "tokens_input", "tokens_output") that belong to
`/v1/chat` and `/v1/agents/run`, plus "documents_processed"/"storage_mb"
that belong to POST /documents -- none of which exist anywhere in this
codebase (Partie 9 -- API publique -- and Partie 2.2.1 are both 0%
built; verified via a repo-wide search, zero references to any /v1/*
route, an agent-run endpoint, or a documents router). record_usage/
get_usage/get_usage_summary (api/security/usage.py) are fully generic
and metric-agnostic -- any caller can record any string metric under
any name. What's real TODAY is which call sites actually invoke them:
workspace creation, team creation, member invitation (both the
immediate-add and email-link accept paths), and a "quota_exceeded"
event each time api/security/quotas.py's require_quota_available denies
a request -- see each call site's own comment for why.
"""

import datetime as dt
import uuid

from sqlalchemy import JSON, Date, DateTime, ForeignKey, Index, Integer, String, UniqueConstraint, func
from sqlalchemy.orm import Mapped, mapped_column

from api.database import Base


class OrganizationUsage(Base):
    __tablename__ = "organization_usage"

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    organization_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("organizations.id", ondelete="CASCADE"), nullable=False)
    date: Mapped[dt.date] = mapped_column(Date, nullable=False)
    metric: Mapped[str] = mapped_column(String(64), nullable=False)
    value: Mapped[int] = mapped_column(Integer, nullable=False, default=0)

    __table_args__ = (
        UniqueConstraint("organization_id", "date", "metric", name="uq_organization_usage_org_date_metric"),
    )


class OrganizationUsageDetail(Base):
    __tablename__ = "organization_usage_details"

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    organization_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("organizations.id", ondelete="CASCADE"), nullable=False)
    # Nullable: a future system-triggered usage event (a scheduled job,
    # a webhook) may have no human user to attribute -- same
    # nullable-FK-with-SET NULL reasoning as AuditLog.user_id.
    user_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("users.id", ondelete="SET NULL"), nullable=True)
    timestamp: Mapped[dt.datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    metric: Mapped[str] = mapped_column(String(64), nullable=False)
    value: Mapped[int] = mapped_column(Integer, nullable=False)
    # Named metadata_json, not `metadata` -- that name collides with
    # SQLAlchemy's own Base.metadata attribute on every declarative
    # model (same reasoning as AuditLog.metadata_json). Uses the
    # generic, cross-dialect sa.JSON type here -- NOT
    # sqlalchemy.dialects.postgresql.JSONB, which the SQLite fast suite
    # (schema built straight from these ORM models via
    # Base.metadata.create_all(), never Alembic) cannot represent at
    # all. That is the exact class of trap Identity() sprung on
    # password_history.sequence earlier this project -- sa.JSON avoids
    # it by compiling to a real JSONB-equivalent on Postgres and to
    # TEXT on SQLite, both transparently (de)serialized to/from a
    # Python dict by SQLAlchemy itself.
    metadata_json: Mapped[dict | None] = mapped_column(JSON, nullable=True)

    __table_args__ = (
        # The only read pattern this table serves (get_usage_summary's
        # detail companion, GET .../usage/details) is always "this
        # org's rows, optionally one metric, optionally a date range" --
        # never metric or timestamp alone across all organizations.
        Index("ix_organization_usage_details_org_metric_timestamp", "organization_id", "metric", "timestamp"),
    )
