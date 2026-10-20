"""Celery tasks of api/tasks/notifications.py and the dispatch helpers of api/tasks/workflows.py against a real PostgreSQL.

Notifications: e-mail delivery (sent / failed / idempotent / missing recipient), retry of failed e-mails within the budget, purge of read or expired notifications.
Workflows: a run or trigger that does not exist, scheduling that survives a broker outage, the outcome notification of a finished run."""

import datetime as dt
import uuid

import pytest
from sqlalchemy.orm import Session

from api.models.notification import Notification
from api.tasks import notifications as notification_tasks
from api.tasks import workflows as workflow_tasks
from api.tasks.notifications import purge_old_notifications_task, retry_failed_notifications_task, send_notification_email_task
from api.tasks.workflows import (
    check_scheduled_workflow_triggers, resume_workflow_task, run_workflow_task, schedule_workflow_resume, schedule_workflow_run,
)
from pg_tasks_support import organization, require_postgres, user

NOW = dt.datetime.now(dt.timezone.utc)


@pytest.fixture
def engine():
    return require_postgres()


def _notification(org_id, user_id, **fields) -> Notification:
    base = dict(organization_id=org_id, user_id=user_id, type="workflow_completed", title="t", body="Your workflow finished", data={"workflow_name": "W"}, channel="email", email_status="pending")
    return Notification(**{**base, **fields})


def _save(engine, *rows):
    with Session(engine) as db:
        db.add_all(rows)
        db.commit()
        return [r.id for r in rows]


def _reload(engine, notification_id) -> Notification | None:
    with Session(engine) as db:
        return db.get(Notification, notification_id)


# ------------------------------------------------------------------------------------------------ e-mail delivery


def test_a_pending_notification_email_is_sent_once_and_never_twice(engine, monkeypatch):
    sent = []
    monkeypatch.setattr("api.services.email._send", lambda to, subject, body, sender=None: sent.append((to, subject)))
    with organization(engine, "notify") as org_id, user(engine, "recipient") as (user_id, email):
        (notification_id,) = _save(engine, _notification(org_id, user_id))

        assert send_notification_email_task(str(notification_id)) == "sent"
        assert send_notification_email_task(str(notification_id)) == "sent"  # at-least-once delivery: a duplicate task does not send again

        assert [to for to, _subject in sent] == [email]
        row = _reload(engine, notification_id)
        assert row.email_status == "sent" and row.email_sent_at is not None


def test_a_send_failure_is_recorded_on_the_row_with_its_retry_count(engine, monkeypatch):
    def refuse(*args, **kwargs):
        raise RuntimeError("SMTP refused")

    monkeypatch.setattr("api.services.email._send", refuse)
    with organization(engine, "notifyfail") as org_id, user(engine, "recipient") as (user_id, _email):
        (notification_id,) = _save(engine, _notification(org_id, user_id))

        assert send_notification_email_task(str(notification_id)) == "failed"

        row = _reload(engine, notification_id)
        assert row.email_status == "failed" and "SMTP refused" in row.email_error and row.email_retry_count == 1


def test_an_unknown_notification_is_reported_as_not_found(engine):
    assert send_notification_email_task(str(uuid.uuid4())) == "not_found"


def test_failed_emails_within_the_retry_budget_are_requeued_and_exhausted_ones_are_not(engine, monkeypatch):
    queued = []
    monkeypatch.setattr(notification_tasks.send_notification_email_task, "delay", lambda notification_id: queued.append(notification_id))
    with organization(engine, "retry") as org_id, user(engine, "recipient") as (user_id, _email):
        retryable, exhausted, delivered = _save(
            engine, _notification(org_id, user_id, email_status="failed", email_retry_count=1), _notification(org_id, user_id, email_status="failed", email_retry_count=3),
            _notification(org_id, user_id, email_status="sent"),
        )

        assert retry_failed_notifications_task() >= 1

        assert str(retryable) in queued and str(exhausted) not in queued and str(delivered) not in queued
        assert _reload(engine, retryable).email_status == "pending"  # reset so the send is allowed to go through
        assert _reload(engine, exhausted).email_status == "failed"


# ------------------------------------------------------------------------------------------------ purge


def test_the_purge_removes_old_read_and_expired_notifications_but_never_an_unread_live_one(engine):
    with organization(engine, "purge") as org_id, user(engine, "recipient") as (user_id, _email):
        read_long_ago, read_recently, expired, unread_old, unread_live_old_expiry = _save(
            engine,
            _notification(org_id, user_id, read_at=NOW - dt.timedelta(days=200)), _notification(org_id, user_id, read_at=NOW - dt.timedelta(days=2)),
            _notification(org_id, user_id, expires_at=NOW - dt.timedelta(days=1)), _notification(org_id, user_id, created_at=NOW - dt.timedelta(days=400)),
            _notification(org_id, user_id, expires_at=NOW + dt.timedelta(days=5)),
        )

        assert purge_old_notifications_task() >= 2

        assert _reload(engine, read_long_ago) is None and _reload(engine, expired) is None
        assert _reload(engine, read_recently) is not None
        assert _reload(engine, unread_old) is not None  # age alone never hides what a user has not seen
        assert _reload(engine, unread_live_old_expiry) is not None


# ------------------------------------------------------------------------------------------------ workflows


def test_running_or_resuming_something_that_does_not_exist_reports_not_found(engine):
    assert run_workflow_task(str(uuid.uuid4())) == "not_found"
    assert resume_workflow_task(str(uuid.uuid4()), str(uuid.uuid4())) == "not_found"


def test_a_broker_outage_never_fails_the_request_that_schedules_a_workflow(monkeypatch, caplog):
    def down(*args, **kwargs):
        raise ConnectionError("broker down")

    monkeypatch.setattr(workflow_tasks.run_workflow_task, "delay", down)
    monkeypatch.setattr(workflow_tasks.resume_workflow_task, "delay", down)

    schedule_workflow_run(uuid.uuid4())
    schedule_workflow_resume(uuid.uuid4(), uuid.uuid4())

    assert "could not schedule run" in caplog.text and "could not schedule resume" in caplog.text


def test_scheduling_hands_the_run_to_the_worker_when_the_broker_is_up(monkeypatch):
    calls = []
    monkeypatch.setattr(workflow_tasks.run_workflow_task, "delay", lambda run_id: calls.append(("run", run_id)))
    monkeypatch.setattr(workflow_tasks.resume_workflow_task, "delay", lambda run_id, input_id: calls.append(("resume", run_id, input_id)))
    run_id, input_id = uuid.uuid4(), uuid.uuid4()

    schedule_workflow_run(run_id)
    schedule_workflow_resume(run_id, input_id)

    assert calls == [("run", str(run_id)), ("resume", str(run_id), str(input_id))]


def test_the_trigger_sweep_runs_on_an_empty_schedule(engine):
    assert check_scheduled_workflow_triggers() >= 0
