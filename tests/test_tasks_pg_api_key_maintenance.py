"""Celery tasks of api/tasks/api_key_maintenance.py against a real PostgreSQL: expiry reminders, automatic removal of expired keys, scheduled rotation, quota resets."""

import datetime as dt
import logging
import uuid

import pytest
from sqlalchemy import select
from sqlalchemy.orm import Session

from api.config import settings
from api.models.organization_api_key import KeyRotationHistory, OrganizationAPIKey
from api.tasks.api_key_maintenance import (
    auto_remove_expired_keys_task, check_expiring_keys_task, execute_scheduled_rotation_task, reset_quotas_task,
)
from pg_tasks_support import organization, require_postgres

NOW = dt.datetime.now(dt.timezone.utc)


@pytest.fixture
def engine():
    return require_postgres()


def _key(org_id, name, **fields) -> OrganizationAPIKey:
    return OrganizationAPIKey(
        organization_id=org_id, name=name, key_hash=uuid.uuid4().hex + uuid.uuid4().hex, key_prefix="pk_", scopes=["search"], **fields,
    )


def _reload(engine, key_id) -> OrganizationAPIKey:
    with Session(engine) as db:
        return db.get(OrganizationAPIKey, key_id)


def test_reminders_count_only_unrevoked_keys_expiring_within_a_reminder_window(engine, caplog, monkeypatch):
    monkeypatch.setattr(settings, "KEY_EXPIRATION_REMINDER_DAYS", [7])
    with organization(engine, "remind") as org_id:
        soon = _key(org_id, "expires-in-3-days", expires_at=NOW + dt.timedelta(days=3))
        later = _key(org_id, "expires-in-30-days", expires_at=NOW + dt.timedelta(days=30))
        already_gone = _key(org_id, "expired-yesterday", expires_at=NOW - dt.timedelta(days=1))
        revoked = _key(org_id, "revoked-but-expiring", expires_at=NOW + dt.timedelta(days=2), revoked_at=NOW)
        never = _key(org_id, "never-expires")
        with Session(engine) as db:
            db.add_all([soon, later, already_gone, revoked, never])
            db.commit()

        with caplog.at_level(logging.WARNING, logger="api.tasks.api_key_maintenance"):
            reminded = check_expiring_keys_task()

        assert reminded >= 1
        text = "\n".join(r.getMessage() for r in caplog.records)
        assert "expires-in-3-days" in text
        for name in ("expires-in-30-days", "expired-yesterday", "revoked-but-expiring", "never-expires"):
            assert name not in text


def test_expired_keys_are_revoked_not_deleted_and_live_keys_are_left_alone(engine, monkeypatch):
    monkeypatch.setattr(settings, "KEY_EXPIRATION_AUTO_REMOVE", True)
    with organization(engine, "expire") as org_id:
        expired = _key(org_id, "expired", expires_at=NOW - dt.timedelta(hours=1))
        live = _key(org_id, "live", expires_at=NOW + dt.timedelta(days=5))
        forever = _key(org_id, "forever")
        with Session(engine) as db:
            db.add_all([expired, live, forever])
            db.commit()
            ids = (expired.id, live.id, forever.id)

        revoked = auto_remove_expired_keys_task()

        assert revoked >= 1
        first_revocation = _reload(engine, ids[0]).revoked_at
        assert first_revocation is not None  # revoked, the row is still there for the audit trail
        assert _reload(engine, ids[1]).revoked_at is None
        assert _reload(engine, ids[2]).revoked_at is None
        auto_remove_expired_keys_task()
        assert _reload(engine, ids[0]).revoked_at == first_revocation  # a second run does not touch it again


def test_automatic_removal_does_nothing_when_the_setting_is_off(engine, monkeypatch):
    monkeypatch.setattr(settings, "KEY_EXPIRATION_AUTO_REMOVE", False)
    with organization(engine, "noremove") as org_id:
        expired = _key(org_id, "expired", expires_at=NOW - dt.timedelta(hours=1))
        with Session(engine) as db:
            db.add(expired)
            db.commit()
            key_id = expired.id

        assert auto_remove_expired_keys_task() == 0
        assert _reload(engine, key_id).revoked_at is None


def test_a_due_scheduled_rotation_replaces_the_key_and_records_the_history(engine, monkeypatch):
    monkeypatch.setattr(settings, "KEY_ROTATION_AUTO_ENABLED", True)
    with organization(engine, "rotate") as org_id:
        due = _key(org_id, "service", scheduled_rotation_at=NOW - dt.timedelta(minutes=5))
        not_due = _key(org_id, "later", scheduled_rotation_at=NOW + dt.timedelta(days=2))
        with Session(engine) as db:
            db.add_all([due, not_due])
            db.commit()
            due_id, not_due_id = due.id, not_due.id

        assert execute_scheduled_rotation_task() >= 1

        old = _reload(engine, due_id)
        assert old.revoked_at is not None and old.scheduled_rotation_at is None
        assert _reload(engine, not_due_id).revoked_at is None
        with Session(engine) as db:
            history = db.scalars(select(KeyRotationHistory).where(KeyRotationHistory.rotated_from == due_id)).one()
            new_key = db.get(OrganizationAPIKey, history.rotated_to)
            assert new_key.name == "service (rotated)" and new_key.revoked_at is None and new_key.scopes == ["search"]
            assert new_key.key_hash != old.key_hash and new_key.organization_id == org_id
            assert history.reason == "scheduled rotation (auto)"


def test_scheduled_rotation_is_inert_when_automatic_rotation_is_off(engine, monkeypatch):
    monkeypatch.setattr(settings, "KEY_ROTATION_AUTO_ENABLED", False)
    with organization(engine, "norotate") as org_id:
        due = _key(org_id, "service", scheduled_rotation_at=NOW - dt.timedelta(minutes=5))
        with Session(engine) as db:
            db.add(due)
            db.commit()
            key_id = due.id

        assert execute_scheduled_rotation_task() == 0
        assert _reload(engine, key_id).revoked_at is None


def test_quota_reset_zeroes_usage_and_schedules_the_next_period(engine):
    with organization(engine, "quota") as org_id:
        monthly = _key(org_id, "monthly", quota_limit=100, quota_period="month", quota_used=90, quota_reset_at=NOW - dt.timedelta(minutes=1))
        yearly = _key(org_id, "yearly", quota_limit=100, quota_period="year", quota_used=50, quota_reset_at=NOW - dt.timedelta(minutes=1))
        daily = _key(org_id, "daily", quota_limit=100, quota_period="day", quota_used=10, quota_reset_at=NOW - dt.timedelta(minutes=1))
        future = _key(org_id, "future", quota_limit=100, quota_period="month", quota_used=70, quota_reset_at=NOW + dt.timedelta(days=3))
        with Session(engine) as db:
            db.add_all([monthly, yearly, daily, future])
            db.commit()
            ids = [k.id for k in (monthly, yearly, daily, future)]

        assert reset_quotas_task() >= 3

        month, year, day, ahead = (_reload(engine, i) for i in ids)
        assert month.quota_used == 0 and 29 <= (month.quota_reset_at - NOW).days <= 30
        assert year.quota_used == 0 and 364 <= (year.quota_reset_at - NOW).days <= 365
        assert day.quota_used == 0 and day.quota_reset_at is None
        assert ahead.quota_used == 70  # its reset date has not come
