"""
Audit findings 18/19/20 -- tests for api/models/audit_log.py,
api/security/audit_log.py, and api/routers/audit.py, against the fast
in-memory SQLite DB (see conftest.py), same pattern as test_auth_api.py.
"""

import datetime as dt

import pyotp
from sqlalchemy import select

from api.config import settings
from api.models.audit_log import AuditAction, AuditLog
from api.models.user import User, UserRole
from api.security.audit_log import log_audit_action, verify_audit_log_integrity


def _admin_auth_header(access_token: str) -> dict:
    return {"Authorization": f"Bearer {access_token}"}


async def _promote_to_admin(db_session, email: str) -> None:
    user = await db_session.scalar(select(User).where(User.email == email))
    user.role = UserRole.admin
    await db_session.commit()


# --------------------------------------------------------- item 18 -----

async def test_register_writes_a_real_audit_log_row(client, register_payload, db_session):
    await client.post("/auth/register", json=register_payload)
    rows = (await db_session.scalars(select(AuditLog).where(AuditLog.action == AuditAction.REGISTER.value))).all()
    assert len(rows) == 1
    assert rows[0].success is True
    assert rows[0].user_id is not None


async def test_login_failure_writes_an_audit_row_with_no_user_id_for_unknown_email(client, db_session):
    await client.post("/auth/login", json={"email": "nobody@example.com", "password": "whatever123"})
    row = await db_session.scalar(select(AuditLog).where(AuditLog.action == AuditAction.LOGIN_FAILED.value))
    assert row is not None
    assert row.user_id is None  # no real account to attach to
    assert row.success is False
    assert row.failure_reason == "invalid_credentials"
    assert "nobody@example.com" in row.metadata_json  # the attempted email, since there's no user_id


async def test_login_success_writes_an_audit_row(client, register_payload, db_session):
    await client.post("/auth/register", json=register_payload)
    await client.post("/auth/login", json={"email": register_payload["email"], "password": register_payload["password"]})
    rows = (await db_session.scalars(select(AuditLog).where(AuditLog.action == AuditAction.LOGIN_SUCCESS.value))).all()
    assert len(rows) == 1
    assert rows[0].success is True


async def test_audit_log_chain_is_verified_intact_after_normal_activity(client, register_payload, db_session):
    await client.post("/auth/register", json=register_payload)
    await client.post("/auth/login", json={"email": register_payload["email"], "password": "wrong-password"})
    await client.post("/auth/login", json={"email": register_payload["email"], "password": register_payload["password"]})

    intact, first_bad_id = await verify_audit_log_integrity(db_session)
    assert intact is True
    assert first_bad_id is None


async def test_audit_log_integrity_check_detects_a_tampered_row(client, register_payload, db_session):
    """Audit finding 18's actual validation criterion: the whole point of
    the hash chain is that altering a historical row after the fact is
    detectable. Simulates exactly that -- direct DB tampering, bypassing
    the application entirely, the same threat model log_audit_action's
    own docstring describes."""
    await client.post("/auth/register", json=register_payload)
    row = await db_session.scalar(select(AuditLog).where(AuditLog.action == AuditAction.REGISTER.value))

    row.failure_reason = "tampered after the fact"  # never touched by the app itself for a successful REGISTER
    await db_session.commit()

    intact, first_bad_id = await verify_audit_log_integrity(db_session)
    assert intact is False
    assert first_bad_id == row.id


async def test_log_audit_action_does_not_lose_the_caller_s_own_pending_changes(client, db_session):
    """Regression test for a real bug caught while building this: an
    earlier version of log_audit_action called db.rollback() when its
    SQLite-incompatible advisory-lock probe failed, which silently
    discarded the CALLER's entire pending transaction (e.g. register()'s
    own not-yet-committed User row) -- not just recovered from the
    failed lock statement. Proven directly here: a row added BEFORE
    calling log_audit_action must still be there after it."""
    user = User(email="pending-write-test@example.com", hashed_password="irrelevant", is_active=True)
    db_session.add(user)
    await db_session.flush()

    await log_audit_action(
        db_session, user_id=user.id, action=AuditAction.LOGIN_SUCCESS, ip="127.0.0.1", user_agent="pytest",
        success=True,
    )
    await db_session.commit()

    still_there = await db_session.scalar(select(User).where(User.email == "pending-write-test@example.com"))
    assert still_there is not None


# --------------------------------------------------------- item 19 -----

async def test_user_can_see_their_own_audit_logs(client, register_payload):
    access_token = (await client.post("/auth/register", json=register_payload)).json()["access_token"]
    response = await client.get("/account/audit-logs", headers=_admin_auth_header(access_token))
    assert response.status_code == 200
    body = response.json()
    assert body["total"] >= 1
    assert any(item["action"] == "register" for item in body["items"])


async def test_user_cannot_see_another_user_s_audit_logs(client, register_payload):
    other = dict(register_payload)
    other["email"] = "someone-else@example.com"
    await client.post("/auth/register", json=other)

    access_token = (await client.post("/auth/register", json=register_payload)).json()["access_token"]
    response = await client.get("/account/audit-logs", headers=_admin_auth_header(access_token))
    body = response.json()

    my_user_id = body["items"][0]["user_id"]
    assert all(item["user_id"] == my_user_id for item in body["items"])


async def test_audit_log_filter_by_action(client, register_payload):
    access_token = (await client.post("/auth/register", json=register_payload)).json()["access_token"]
    await client.post("/auth/login", json={"email": register_payload["email"], "password": "wrong"})

    response = await client.get("/account/audit-logs?action=login_failed", headers=_admin_auth_header(access_token))
    body = response.json()
    assert body["total"] == 1
    assert body["items"][0]["action"] == "login_failed"


async def test_non_admin_gets_404_from_admin_audit_log_endpoint(client, register_payload):
    access_token = (await client.post("/auth/register", json=register_payload)).json()["access_token"]
    response = await client.get("/admin/audit-logs", headers=_admin_auth_header(access_token))
    assert response.status_code == 404


async def test_admin_can_see_every_user_s_audit_logs(client, register_payload, db_session):
    other = dict(register_payload)
    other["email"] = "someone-else-2@example.com"
    await client.post("/auth/register", json=other)

    access_token = (await client.post("/auth/register", json=register_payload)).json()["access_token"]
    await _promote_to_admin(db_session, register_payload["email"])

    response = await client.get("/admin/audit-logs", headers=_admin_auth_header(access_token))
    assert response.status_code == 200
    user_ids = {item["user_id"] for item in response.json()["items"]}
    assert len(user_ids) >= 2  # both accounts' REGISTER rows are visible


# --------------------------------------------------------- item 20 -----

async def test_non_admin_gets_404_from_failed_logins_dashboard(client, register_payload):
    access_token = (await client.post("/auth/register", json=register_payload)).json()["access_token"]
    response = await client.get("/admin/failed-logins", headers=_admin_auth_header(access_token))
    assert response.status_code == 404


async def test_failed_login_dashboard_aggregates_by_ip_and_email(client, register_payload, db_session):
    access_token = (await client.post("/auth/register", json=register_payload)).json()["access_token"]
    await _promote_to_admin(db_session, register_payload["email"])

    for _ in range(3):
        await client.post("/auth/login", json={"email": "target@example.com", "password": "wrong"})

    response = await client.get("/admin/failed-logins", headers=_admin_auth_header(access_token))
    assert response.status_code == 200
    body = response.json()
    assert body["total_failed_attempts"] >= 3
    email_entry = next((e for e in body["by_email"] if e["key"] == "target@example.com"), None)
    assert email_entry is not None
    assert email_entry["count"] == 3


async def test_failed_login_dashboard_respects_the_time_window(client, register_payload, db_session):
    access_token = (await client.post("/auth/register", json=register_payload)).json()["access_token"]
    await _promote_to_admin(db_session, register_payload["email"])

    await log_audit_action(
        db_session, user_id=None, action=AuditAction.LOGIN_FAILED, ip="10.0.0.1", user_agent=None,
        success=False, metadata={"email": "old@example.com"},
    )
    stale = await db_session.scalar(select(AuditLog).where(AuditLog.action == AuditAction.LOGIN_FAILED.value))
    stale.timestamp = dt.datetime.now(dt.timezone.utc) - dt.timedelta(hours=2)
    await db_session.commit()

    response = await client.get("/admin/failed-logins?window_minutes=60", headers=_admin_auth_header(access_token))
    body = response.json()
    assert not any(e["key"] == "old@example.com" for e in body["by_email"])
