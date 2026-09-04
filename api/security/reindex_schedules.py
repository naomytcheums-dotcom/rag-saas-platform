"""
Partie 2.2.15 -- CRUD for a `ReindexSchedule`, plus the real scheduling
orchestration. `schedule_reindex`/`reindex_organization` (Partie
2.2.9, unchanged) do ALL the real reindexing work -- this module only
decides WHEN, reusing Celery's own `crontab` class (already a real
dependency for Beat itself) to parse/evaluate a stored cron pattern,
rather than adding a new cron-parsing library for this one feature.

**Gestion des conflits (vision critique 2), stated honestly**: neither
`reindex_organization` nor `reindex_document` (Partie 2.2.9) track
"already running" state -- a scheduled reindex firing while a manual
one is already in progress for the SAME organization/document results,
at worst, in some real REDUNDANT work (a document processed twice in
close succession), never corruption: `process_document`'s own real
chunk delete-then-recreate (established since Partie 2.1.1) is already
safe under repetition, the same idempotency guarantee 2.2.9 already
relies on for its own "reindexed twice by accident" case. A real,
accepted scope limitation: no distributed lock prevents the redundant
work ITSELF from happening -- given this feature's own real cadence
(schedules meant for hourly/daily cadences, not sub-second), building
real cross-process locking for this narrow overlap is disproportionate
to what this étape actually asks for.
"""

import datetime as dt
import logging
import uuid

from celery.schedules import crontab
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from api.models.document import Document
from api.models.reindex_schedule import ReindexSchedule
from api.security.documents import reindex_document, reindex_organization

logger = logging.getLogger(__name__)


def _crontab_from_pattern(cron_pattern: str) -> crontab:
    """Real, standard 5-field cron parsing via Celery's OWN `crontab`
    (already a real dependency for Beat itself, see api/tasks/celery_app.py)
    -- no new cron-parsing library needed for this one feature. Raises
    ValueError for anything that isn't exactly 5 real fields, the same
    real, synchronous, "reject bad input before it's ever persisted"
    convention every other create function in this codebase already
    follows."""
    fields = cron_pattern.split()
    if len(fields) != 5:
        raise ValueError(f"cron_pattern must have exactly 5 fields (minute hour day_of_month month_of_year day_of_week), got {cron_pattern!r}")
    minute, hour, day_of_month, month_of_year, day_of_week = fields
    try:
        return crontab(minute=minute, hour=hour, day_of_month=day_of_month, month_of_year=month_of_year, day_of_week=day_of_week)
    except Exception as exc:
        raise ValueError(f"'{cron_pattern}' is not a real, valid cron pattern: {exc}") from exc


def _compute_next_run_at(cron_pattern: str, reference: dt.datetime) -> dt.datetime:
    remaining = _crontab_from_pattern(cron_pattern).remaining_estimate(reference)
    return dt.datetime.now(dt.timezone.utc) + remaining


# =============================================================== CRUD ===============================================================

async def create_reindex_schedule(db: AsyncSession, organization_id: uuid.UUID, schedule_name: str, cron_pattern: str, enabled: bool) -> ReindexSchedule:
    """Item 1's own literal route's real backing function."""
    next_run_at = _compute_next_run_at(cron_pattern, dt.datetime.now(dt.timezone.utc)) if enabled else None
    schedule = ReindexSchedule(
        organization_id=organization_id, schedule_name=schedule_name, cron_pattern=cron_pattern, enabled=enabled, next_run_at=next_run_at,
    )
    db.add(schedule)
    await db.flush()
    return schedule


async def list_reindex_schedules(db: AsyncSession, organization_id: uuid.UUID) -> list[ReindexSchedule]:
    return (await db.scalars(
        select(ReindexSchedule).where(ReindexSchedule.organization_id == organization_id).order_by(ReindexSchedule.created_at.desc())
    )).all()


async def get_reindex_schedule_or_raise(db: AsyncSession, schedule_id: uuid.UUID) -> ReindexSchedule:
    schedule = await db.get(ReindexSchedule, schedule_id)
    if schedule is None:
        raise ValueError(f"'{schedule_id}' is not a registered reindex schedule")
    return schedule


async def update_reindex_schedule(
    db: AsyncSession, schedule_id: uuid.UUID, schedule_name: str | None = None, cron_pattern: str | None = None, enabled: bool | None = None,
) -> ReindexSchedule:
    """Item 4's own literal `PATCH /reindex-schedules/{schedule_id}`
    real backing function -- every field optional, same real partial-
    update shape as every other PATCH in this codebase (e.g. Partie
    2.2.6's own update_tag)."""
    schedule = await get_reindex_schedule_or_raise(db, schedule_id)
    if schedule_name is not None:
        schedule.schedule_name = schedule_name
    if cron_pattern is not None:
        schedule.cron_pattern = cron_pattern
    if enabled is not None:
        schedule.enabled = enabled
    if cron_pattern is not None or enabled is not None:
        schedule.next_run_at = _compute_next_run_at(schedule.cron_pattern, schedule.last_run_at or dt.datetime.now(dt.timezone.utc)) if schedule.enabled else None
    await db.flush()
    return schedule


async def delete_reindex_schedule(db: AsyncSession, schedule_id: uuid.UUID) -> None:
    schedule = await get_reindex_schedule_or_raise(db, schedule_id)
    await db.delete(schedule)
    await db.flush()


# =========================================================== scheduling ============================================================

async def schedule_reindex(db: AsyncSession, schedule_id: uuid.UUID) -> int:
    """Item 3's own literal function -- runs THIS schedule's own real,
    unchanged org-wide reindex (Partie 2.2.9's reindex_organization,
    `triggered_by=None`: an automated run has no real human actor),
    then advances `last_run_at`/`next_run_at` for real, from the moment
    this run actually happened -- never silently left stale."""
    schedule = await get_reindex_schedule_or_raise(db, schedule_id)
    scheduled_count = await reindex_organization(db, schedule.organization_id, triggered_by=None)
    now = dt.datetime.now(dt.timezone.utc)
    schedule.last_run_at = now
    schedule.next_run_at = _compute_next_run_at(schedule.cron_pattern, now) if schedule.enabled else None
    await db.flush()
    return scheduled_count


async def check_scheduled_reindexes(db: AsyncSession) -> list[ReindexSchedule]:
    """Item 3's own literal function -- every real, ENABLED schedule,
    system-wide, whose own real cron pattern is due right now (a
    schedule that has never run is compared against its own
    `created_at`, the real moment it started existing)."""
    schedules = (await db.scalars(select(ReindexSchedule).where(ReindexSchedule.enabled.is_(True)))).all()
    due = []
    for schedule in schedules:
        reference = schedule.last_run_at or schedule.created_at
        if _crontab_from_pattern(schedule.cron_pattern).is_due(reference).is_due:
            due.append(schedule)
    return due


async def check_scheduled_document_reindexes(db: AsyncSession) -> list[Document]:
    """The real, per-document counterpart to `check_scheduled_reindexes`
    above -- every real, non-deleted document with its OWN
    `reindex_schedule` set, due right now against its own
    `indexing_started_at` (Partie 2.2.11's own real "last run" column,
    reused rather than duplicated -- see Document.reindex_schedule's
    own docstring)."""
    documents = (await db.scalars(
        select(Document).where(Document.reindex_schedule.is_not(None), Document.deleted_at.is_(None))
    )).all()
    due = []
    for document in documents:
        reference = document.indexing_started_at or document.created_at
        if _crontab_from_pattern(document.reindex_schedule).is_due(reference).is_due:
            due.append(document)
    return due


async def run_scheduled_reindexes(db: AsyncSession) -> dict:
    """Item 3's own literal function -- executes every real schedule
    AND every real per-document override currently due, system-wide.
    Vision critique 3's own "que se passe-t-il si la réindexation
    échoue" answer: the SAME real "one item's own failure never blocks
    the rest" resilience as every other bulk operation in this
    codebase -- confirmed by a real test where one of several due
    schedules fails.

    Commits per item, not once at the very end -- the exact same real
    bug class already caught and fixed in Partie 2.2.13/2.2.14's own
    periodic tasks: a failure that happened after a real, partial
    `flush()` leaves the session's OWN transaction unusable until
    rolled back, and a rollback that came too late would silently undo
    every OTHER item already successfully reindexed earlier in this
    same sweep.
    """
    ran = 0
    failed = 0

    for schedule in await check_scheduled_reindexes(db):
        try:
            await schedule_reindex(db, schedule.id)
            await db.commit()
            ran += 1
        except Exception as exc:  # noqa: BLE001 -- one schedule's own real failure must never abort the whole sweep
            logger.warning("run_scheduled_reindexes: schedule '%s' failed: %s", schedule.id, exc)
            await db.rollback()
            failed += 1

    for document in await check_scheduled_document_reindexes(db):
        try:
            await reindex_document(db, document.id, triggered_by=None)
            await db.commit()
            ran += 1
        except Exception as exc:  # noqa: BLE001 -- same real per-item resilience
            logger.warning("run_scheduled_reindexes: per-document schedule for '%s' failed: %s", document.id, exc)
            await db.rollback()
            failed += 1

    return {"ran": ran, "failed": failed}
