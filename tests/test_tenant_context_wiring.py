"""The tenant context (api/db_tenant_context.py) is declared exactly when a caller's membership is verified, never for a non-member, and
costs nothing on SQLite. The PostgreSQL behaviour itself is proven in tests/test_postgres_tenant_rls.py (opt-in, disposable database)."""

import uuid

from api import db_tenant_context
from test_document_idor import make_tenants


async def test_a_member_request_declares_its_organization(client, db_session, monkeypatch):
    (owner, org_a, _user_a), (attacker, org_b, _user_b) = await make_tenants(client, db_session, monkeypatch, "tenantctx")
    declared = []
    original = db_tenant_context.bind_tenant

    async def recording(db, org_id):
        declared.append(uuid.UUID(str(org_id)))
        await original(db, org_id)

    monkeypatch.setattr(db_tenant_context, "bind_tenant", recording)

    response = await client.get(f"/organizations/{org_a}/documents", headers=owner)

    assert response.status_code == 200, response.text
    assert declared == [uuid.UUID(str(org_a))]


async def test_a_non_member_never_gets_a_tenant_context_for_the_foreign_organization(client, db_session, monkeypatch):
    (owner, org_a, _user_a), (attacker, org_b, _user_b) = await make_tenants(client, db_session, monkeypatch, "tenantctx2")
    declared = []

    async def recording(db, org_id):
        declared.append(str(org_id))

    monkeypatch.setattr(db_tenant_context, "bind_tenant", recording)

    response = await client.get(f"/organizations/{org_a}/documents", headers=attacker)

    assert response.status_code == 404
    assert declared == []  # the context is only ever declared AFTER the membership check passed


async def test_binding_is_a_pure_memory_operation_on_sqlite(db_session):
    org_id = uuid.uuid4()
    await db_tenant_context.bind_tenant(db_session, org_id)
    assert db_session.sync_session.info["tenant_org_id"] == str(org_id)
    db_tenant_context.clear_tenant(db_session)
    assert "tenant_org_id" not in db_session.sync_session.info
