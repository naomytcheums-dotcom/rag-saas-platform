"""Celery tasks of api/tasks/compliance.py and api/tasks/integrations.py against a real PostgreSQL.

Compliance: breach notification (scope = the organization's verified users, stamped once), stale data-rights requests, the monthly DPO report.
Integrations: log retention, the failed-sync sweep (one connection's failure never aborts the others), the Airbyte sync sweep (not configured is a no-op)."""

import datetime as dt
import logging
import uuid

import pytest
from sqlalchemy import select, text
from sqlalchemy.orm import Session

from api.config import settings
from api.models.compliance import DataBreach, DataRequest, DataRequestStatus, DataRequestType
from api.models.integrations import AirbyteConnection, IntegrationConnection, IntegrationLog, IntegrationLogStatus
from api.models.organization import OrganizationMember, OrganizationRole
from api.models.user import User
from api.services import airbyte_client
from api.tasks.compliance import generate_monthly_compliance_report, process_pending_data_requests, send_data_breach_notifications
from api.tasks.integrations import cleanup_integration_logs, process_integration_webhooks, retry_failed_syncs, sync_integrations
from pg_tasks_support import organization, require_postgres, user

NOW = dt.datetime.now(dt.timezone.utc)


@pytest.fixture
def engine():
    return require_postgres()


# ------------------------------------------------------------------------------------------------ compliance


def test_a_breach_notifies_only_the_verified_users_of_its_organization_and_only_once(engine, monkeypatch):
    sent = []
    monkeypatch.setattr("api.tasks.compliance.send_security_alert_email", lambda to, message: sent.append((to, message)))
    with organization(engine, "breach") as org_id, user(engine, "verified") as (verified_id, verified_email), user(engine, "unverified") as (unverified_id, _), user(engine, "outsider") as (_outsider, outsider_email):
        with Session(engine) as db:
            db.get(User, verified_id).is_email_verified = True
            db.get(User, _outsider).is_email_verified = True
            db.add_all([OrganizationMember(organization_id=org_id, user_id=verified_id), OrganizationMember(organization_id=org_id, user_id=unverified_id)])
            breach = DataBreach(description="credentials leaked " + "x" * 300, organization_id=org_id)
            db.add(breach)
            db.commit()
            breach_id = str(breach.id)

        assert send_data_breach_notifications(breach_id) == 1
        assert send_data_breach_notifications(breach_id) == 0  # already notified: never notify twice

        assert [to for to, _ in sent] == [verified_email] and outsider_email not in [to for to, _ in sent]
        assert len(sent[0][1]) < 260  # the description is cut in the mail
        with Session(engine) as db:
            assert db.get(DataBreach, uuid.UUID(breach_id)).notified_at is not None
            db.execute(text("DELETE FROM data_breaches WHERE id = :i"), {"i": breach_id})
            db.commit()


def test_one_bad_address_does_not_stop_the_notification_sweep(engine, monkeypatch):
    attempts = []

    def flaky(to, message):
        attempts.append(to)
        if "bad" in to:
            raise RuntimeError("mailbox full")

    monkeypatch.setattr("api.tasks.compliance.send_security_alert_email", flaky)
    with organization(engine, "flaky") as org_id, user(engine, "bad") as (bad_id, _bad_email), user(engine, "good") as (good_id, good_email):
        with Session(engine) as db:
            for uid in (bad_id, good_id):
                db.get(User, uid).is_email_verified = True
                db.add(OrganizationMember(organization_id=org_id, user_id=uid))
            breach = DataBreach(description="incident", organization_id=org_id)
            db.add(breach)
            db.commit()
            breach_id = breach.id

        assert send_data_breach_notifications(str(breach_id)) == 1  # the good address is notified, the failure is only logged
        assert good_email in attempts

        with Session(engine) as db:
            assert db.get(DataBreach, breach_id).notified_at is not None
            db.execute(text("DELETE FROM data_breaches WHERE id = :i"), {"i": breach_id})
            db.commit()


def test_an_unknown_breach_notifies_nobody(engine):
    assert send_data_breach_notifications(str(uuid.uuid4())) == 0


def test_stale_pending_data_requests_are_flagged_in_the_log(engine, caplog):
    with user(engine, "requester") as (user_id, _email):
        with Session(engine) as db:
            stale = DataRequest(user_id=user_id, request_type=DataRequestType.access, status=DataRequestStatus.pending, created_at=NOW - dt.timedelta(days=9))
            fresh = DataRequest(user_id=user_id, request_type=DataRequestType.erasure, status=DataRequestStatus.pending, created_at=NOW - dt.timedelta(days=1))
            done = DataRequest(user_id=user_id, request_type=DataRequestType.portability, status=DataRequestStatus.completed, created_at=NOW - dt.timedelta(days=30))
            db.add_all([stale, fresh, done])
            db.commit()
            stale_id = stale.id

        with caplog.at_level(logging.WARNING, logger="api.tasks.compliance"):
            assert process_pending_data_requests() >= 1

        assert str(stale_id) in caplog.text


def test_the_monthly_report_counts_open_items_and_is_mailed_to_the_dpo_when_configured(engine, monkeypatch):
    sent = []
    monkeypatch.setattr("api.tasks.compliance.send_security_alert_email", lambda to, message: sent.append((to, message)))
    monkeypatch.setattr(settings, "DPO_EMAIL", None)
    report = generate_monthly_compliance_report()
    assert set(report) == {"pending_data_requests", "unnotified_breaches", "generated_at"} and sent == []

    monkeypatch.setattr(settings, "DPO_EMAIL", "dpo@example.test")
    generate_monthly_compliance_report()
    assert sent and sent[0][0] == "dpo@example.test" and "Monthly compliance report" in sent[0][1]

    def boom(*args):
        raise RuntimeError("mail provider down")

    monkeypatch.setattr("api.tasks.compliance.send_security_alert_email", boom)
    assert generate_monthly_compliance_report()["generated_at"]  # a mail failure never loses the report


# ------------------------------------------------------------------------------------------------ integrations


def _connection(org_id, **fields) -> IntegrationConnection:
    return IntegrationConnection(**{"organization_id": org_id, "name": "hook", "token": uuid.uuid4().hex, **fields})


def test_integration_logs_past_the_retention_window_are_purged(engine):
    with organization(engine, "intlogs") as org_id:
        with Session(engine) as db:
            connection = _connection(org_id)
            db.add(connection)
            db.flush()
            old = IntegrationLog(connection_id=connection.id, status=IntegrationLogStatus.accepted, payload={}, created_at=NOW - dt.timedelta(days=settings.INTEGRATION_LOG_RETENTION_DAYS + 3))
            fresh = IntegrationLog(connection_id=connection.id, status=IntegrationLogStatus.error, payload={}, created_at=NOW - dt.timedelta(days=1))
            db.add_all([old, fresh])
            db.commit()
            old_id, fresh_id = old.id, fresh.id

        assert cleanup_integration_logs() >= 1

        with Session(engine) as db:
            assert db.get(IntegrationLog, old_id) is None and db.get(IntegrationLog, fresh_id) is not None


def test_the_failed_sync_sweep_retries_active_connections_and_survives_one_failing(engine, monkeypatch):
    with organization(engine, "retry") as org_id:
        with Session(engine) as db:
            good, broken, inactive = _connection(org_id, name="good"), _connection(org_id, name="broken"), _connection(org_id, name="off", is_active=False)
            db.add_all([good, broken, inactive])
            db.commit()
            ids = {c.name: c.id for c in (good, broken, inactive)}

        seen = []

        async def retry(db, connection):
            seen.append(connection.id)
            if connection.id == ids["broken"]:
                raise RuntimeError("mapping still wrong")
            return [object(), object()]

        monkeypatch.setattr("api.services.integrations.retry_failed_logs", retry)

        result = retry_failed_syncs()

        assert ids["good"] in seen and ids["broken"] in seen and ids["off"] not in seen
        assert result["connections_failed"] >= 1 and result["logs_retried"] >= 2
        assert process_integration_webhooks()["connections_checked"] >= 2  # the second task name runs the same sweep


def test_the_airbyte_sweep_triggers_each_connection_and_stops_quietly_when_not_configured(engine, monkeypatch):
    with organization(engine, "airbyte") as org_id:
        with Session(engine) as db:
            db.add_all([AirbyteConnection(organization_id=org_id, name=n, airbyte_source_id="s", airbyte_connection_id=f"conn-{n}", source_type="postgres") for n in ("a", "b")])
            db.commit()
        triggered = []

        async def trigger(connection_id):
            triggered.append(connection_id)
            if connection_id == "conn-b":
                raise RuntimeError("airbyte 500")
            return {}

        monkeypatch.setattr(airbyte_client, "trigger_sync", trigger)
        result = sync_integrations()
        assert {"conn-a", "conn-b"} <= set(triggered) and result["syncs_triggered"] >= 1 and result["connections_failed"] >= 1

        async def not_configured(connection_id):
            raise airbyte_client.AirbyteNotConfiguredError("AIRBYTE_API_URL is not set")

        monkeypatch.setattr(airbyte_client, "trigger_sync", not_configured)
        assert sync_integrations()["syncs_triggered"] == 0  # an honest no-op, not a task failure
