"""
Partie 2.2.15 -- a named, organization-wide cron schedule for
automatically re-running Partie 2.2.9's own `reindex_organization`
(itself just a real fan-out to `process_document`, unchanged) --
scheduled, unattended reindexing, rather than only ever a manual
Admin-triggered one.
"""

import datetime as dt
import uuid

from sqlalchemy import Boolean, DateTime, ForeignKey, Index, String, func
from sqlalchemy.orm import Mapped, mapped_column

from api.database import Base


class ReindexSchedule(Base):
    __tablename__ = "reindex_schedules"

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    organization_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("organizations.id", ondelete="CASCADE"), nullable=False)
    schedule_name: Mapped[str] = mapped_column(String(200), nullable=False)
    # A real, standard 5-field cron pattern ("minute hour day_of_month
    # month_of_year day_of_week", e.g. "0 2 * * *") -- validated at
    # creation time by api/security/reindex_schedules.py's own
    # _crontab_from_pattern, which parses it via Celery's OWN
    # `celery.schedules.crontab` (already a real dependency of this
    # codebase for Beat itself -- no new cron-parsing library needed).
    cron_pattern: Mapped[str] = mapped_column(String(100), nullable=False)
    enabled: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    last_run_at: Mapped[dt.datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    next_run_at: Mapped[dt.datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    created_at: Mapped[dt.datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[dt.datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())

    __table_args__ = (
        Index("ix_reindex_schedules_organization_id", "organization_id"),
    )
