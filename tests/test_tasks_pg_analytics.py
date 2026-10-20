"""Celery tasks of api/tasks/analytics.py against a real PostgreSQL: period rollups, retention cleanup, the owner's report e-mail."""

import datetime as dt
import uuid

import pytest
from sqlalchemy import select
from sqlalchemy.orm import Session

from api.config import settings
from api.models.analytics import AnalyticsAggregate, AnalyticsEvent
from api.models.organization import OrganizationMember, OrganizationRole
from api.tasks.analytics import (
    _period_bounds, aggregate_metrics_daily, aggregate_metrics_hourly, aggregate_metrics_monthly, cleanup_old_events, send_analytics_report,
)
from pg_tasks_support import organization, require_postgres, user

FIXED = dt.datetime(2026, 3, 15, 10, 30, 45, tzinfo=dt.timezone.utc)


@pytest.fixture
def engine():
    return require_postgres()


def test_period_bounds_cover_the_period_that_just_elapsed():
    assert _period_bounds("hour", FIXED) == (dt.datetime(2026, 3, 15, 9, tzinfo=dt.timezone.utc), dt.datetime(2026, 3, 15, 10, tzinfo=dt.timezone.utc))
    assert _period_bounds("day", FIXED) == (dt.datetime(2026, 3, 14, tzinfo=dt.timezone.utc), dt.datetime(2026, 3, 15, tzinfo=dt.timezone.utc))
    assert _period_bounds("month", FIXED) == (dt.datetime(2026, 2, 1, tzinfo=dt.timezone.utc), dt.datetime(2026, 3, 1, tzinfo=dt.timezone.utc))
    assert _period_bounds("month", dt.datetime(2026, 1, 3, tzinfo=dt.timezone.utc))[0] == dt.datetime(2025, 12, 1, tzinfo=dt.timezone.utc)  # across the year boundary
    with pytest.raises(ValueError, match="unsupported period"):
        _period_bounds("week", FIXED)


def _event(org_id, event_type, created_at) -> AnalyticsEvent:
    return AnalyticsEvent(organization_id=org_id, event_type=event_type, event_data={}, created_at=created_at)


def test_the_daily_rollup_counts_yesterdays_events_per_type_and_is_idempotent(engine):
    now = dt.datetime.now(dt.timezone.utc)
    start, _end = _period_bounds("day", now)
    with organization(engine, "rollup") as org_id:
        with Session(engine) as db:
            db.add_all([
                _event(org_id, "chat", start + dt.timedelta(hours=1)), _event(org_id, "chat", start + dt.timedelta(hours=2)), _event(org_id, "upload", start + dt.timedelta(hours=3)),
                _event(org_id, "chat", start - dt.timedelta(hours=1)),  # the day before: not counted
                _event(org_id, "chat", now),  # today: not counted yet
            ])
            db.commit()

        assert aggregate_metrics_daily() >= 3
        aggregate_metrics_daily()  # the same period is overwritten, never duplicated

        with Session(engine) as db:
            rows = db.scalars(select(AnalyticsAggregate).where(AnalyticsAggregate.organization_id == org_id, AnalyticsAggregate.period == "day")).all()
            assert {r.metric_name: r.metric_value for r in rows} == {"event_count.total": 3, "event_count.chat": 2, "event_count.upload": 1}
            assert all(r.period_start == start for r in rows)


def test_the_hourly_and_monthly_rollups_run_on_their_own_periods(engine):
    with organization(engine, "periods") as org_id:
        aggregate_metrics_hourly()
        aggregate_metrics_monthly()
        with Session(engine) as db:
            periods = {r.period for r in db.scalars(select(AnalyticsAggregate).where(AnalyticsAggregate.organization_id == org_id))}
        assert periods == {"hour", "month"}  # an organization with no events still gets its zero total


def test_the_rollup_is_a_no_op_when_disabled(engine, monkeypatch):
    monkeypatch.setattr(settings, "ANALYTICS_AGGREGATION_ENABLED", False)
    with organization(engine, "off") as org_id:
        assert aggregate_metrics_daily() == 0
        with Session(engine) as db:
            assert db.scalars(select(AnalyticsAggregate).where(AnalyticsAggregate.organization_id == org_id)).all() == []


def test_cleanup_deletes_old_events_but_keeps_recent_ones_and_the_rollups(engine):
    now = dt.datetime.now(dt.timezone.utc)
    with organization(engine, "cleanup") as org_id:
        with Session(engine) as db:
            old, recent = _event(org_id, "chat", now - dt.timedelta(days=400)), _event(org_id, "chat", now - dt.timedelta(days=2))
            rollup = AnalyticsAggregate(organization_id=org_id, metric_name="event_count.total", metric_value=5, period="day", period_start=now - dt.timedelta(days=500))
            db.add_all([old, recent, rollup])
            db.commit()
            old_id, recent_id, rollup_id = old.id, recent.id, rollup.id

        assert cleanup_old_events() >= 1
        assert cleanup_old_events(days=1) >= 1  # an explicit window overrides the configured retention

        with Session(engine) as db:
            assert db.get(AnalyticsEvent, old_id) is None
            assert db.get(AnalyticsEvent, recent_id) is None  # 2 days old, past the explicit 1-day window
            assert db.get(AnalyticsAggregate, rollup_id) is not None  # a rollup outlives the raw events


def test_the_report_goes_to_the_owner_and_never_raises(engine, monkeypatch):
    sent = []
    monkeypatch.setattr("api.services.email_branding.send_branded_analytics_report_email_sync", lambda db, org_id, email, total: sent.append((org_id, email, total)))
    with organization(engine, "report") as org_id, organization(engine, "noowner") as ownerless_org, user(engine, "owner") as (owner_id, owner_email):
        with Session(engine) as db:
            db.add(OrganizationMember(organization_id=org_id, user_id=owner_id, role=OrganizationRole.owner))
            db.add_all([_event(org_id, "chat", dt.datetime.now(dt.timezone.utc) - dt.timedelta(days=d)) for d in (1, 5, 45)])  # 45 days ago is outside the 30-day window
            db.commit()

        assert send_analytics_report(str(org_id)) is True
        assert sent == [(org_id, owner_email, 2)]
        assert send_analytics_report(str(ownerless_org)) is False

        def boom(*args):
            raise RuntimeError("mail provider down")

        monkeypatch.setattr("api.services.email_branding.send_branded_analytics_report_email_sync", boom)
        assert send_analytics_report(str(org_id)) is False
        assert uuid.UUID(str(org_id)) == org_id
