"""R1: refused attempts on the superadmin-only financial routes are audited for platform staff only, once per minute per route.

Before: any authenticated caller (an ordinary user included) wrote and committed one audit row per refused request, so anybody could
grow the audit table without limit and contend for the audit chain lock. Now only a platform admin leaves a row (the interesting
case: staff trying a financial write), deduplicated per (user, route template, minute); an ordinary user gets the same 403 and a
log line, and an anonymous caller never reaches the dependency.
"""

import logging
import uuid

from sqlalchemy import func, select

from api.models.audit_log import AuditLog
from api.models.user import UserRole
from test_document_idor import make_tenants
from test_p1_backoffice_and_suspension import _bearer, _platform_user

ACTION = "admin_financial_action_denied"


async def _denied_rows(db_session):
    db_session.expire_all()
    return await db_session.scalar(select(func.count()).select_from(AuditLog).where(AuditLog.action == ACTION))


async def test_an_ordinary_user_gets_403_and_writes_nothing(client, db_session, monkeypatch, caplog):
    (headers, _org, _user), _other = await make_tenants(client, db_session, monkeypatch, "r1user")
    with caplog.at_level(logging.WARNING):
        for _ in range(5):
            assert (await client.post("/admin/plans", json={"key": "k", "name": "K"}, headers=headers)).status_code == 403
    assert await _denied_rows(db_session) == 0
    assert any("superadmin-only" in record.getMessage() for record in caplog.records), "the refusal must still leave a log line"


async def test_an_anonymous_caller_writes_nothing(client, db_session):
    for _ in range(3):
        assert (await client.post("/admin/plans", json={"key": "k", "name": "K"})).status_code in (401, 403)
    assert await _denied_rows(db_session) == 0


async def test_a_platform_admin_is_audited_once(client, db_session):
    admin = await _platform_user(db_session, "r1-admin-once@example.com", UserRole.admin)
    admin_id, headers = admin.id, _bearer(admin.id)
    assert (await client.post("/admin/plans", json={"key": "k", "name": "K"}, headers=headers)).status_code == 403
    db_session.expire_all()
    rows = (await db_session.scalars(select(AuditLog).where(AuditLog.action == ACTION))).all()
    assert len(rows) == 1 and rows[0].user_id == admin_id and rows[0].success is False and '"role": "admin"' in rows[0].metadata_json


async def test_a_repeating_admin_is_deduplicated_per_route_and_minute(client, db_session):
    admin = await _platform_user(db_session, "r1-admin-repeat@example.com", UserRole.admin)
    headers = _bearer(admin.id)
    for _ in range(5):
        assert (await client.post("/admin/plans", json={"key": "k", "name": "K"}, headers=headers)).status_code == 403
    assert await _denied_rows(db_session) == 1, "five identical refusals inside a minute must leave one row"

    # another route is another row; changing the identifiers inside the same route template does not open a new row
    for _ in range(3):
        assert (await client.post(f"/admin/subscriptions/{uuid.uuid4()}/extend", json={"days": 5}, headers=headers)).status_code == 403
    assert await _denied_rows(db_session) == 2
