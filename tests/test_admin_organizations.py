"""Partie 11.2 -- platform-admin organization management."""


def _auth_header(access_token: str) -> dict:
    return {"Authorization": f"Bearer {access_token}"}


async def _make_admin_and_org(client, db_session, register_payload):
    from sqlalchemy import select

    from api.models.user import User, UserRole

    token = (await client.post("/auth/register", json=register_payload)).json()["access_token"]
    user = await db_session.scalar(select(User).where(User.email == register_payload["email"]))
    org_id = (await client.post("/organizations", json={"name": "Admin Test Org"}, headers=_auth_header(token))).json()["id"]
    user.role = UserRole.admin
    await db_session.commit()
    return token, user, org_id


async def test_list_and_get_organization_admin(client, db_session, register_payload):
    token, _, org_id = await _make_admin_and_org(client, db_session, register_payload)

    listing = await client.get("/admin/organizations", headers=_auth_header(token))
    assert listing.status_code == 200
    assert listing.json()["total"] >= 1

    detail = await client.get(f"/admin/organizations/{org_id}", headers=_auth_header(token))
    assert detail.status_code == 200
    assert detail.json()["is_suspended"] is False


async def test_suspend_and_activate_organization(client, db_session, register_payload):
    token, _, org_id = await _make_admin_and_org(client, db_session, register_payload)

    suspend_response = await client.post(f"/admin/organizations/{org_id}/suspend", json={"reason": "TOS violation"}, headers=_auth_header(token))
    assert suspend_response.status_code == 200
    assert suspend_response.json()["is_suspended"] is True
    assert suspend_response.json()["suspended_reason"] == "TOS violation"

    activate_response = await client.post(f"/admin/organizations/{org_id}/activate", headers=_auth_header(token))
    assert activate_response.status_code == 200
    assert activate_response.json()["is_suspended"] is False


async def test_suspend_is_audited(client, db_session, register_payload):
    token, _, org_id = await _make_admin_and_org(client, db_session, register_payload)
    await client.post(f"/admin/organizations/{org_id}/suspend", json={"reason": "test"}, headers=_auth_header(token))

    logs = await client.get(f"/admin/organizations/{org_id}/activity", headers=_auth_header(token))
    assert logs.status_code == 200
    actions = {item["action"] for item in logs.json()["items"]}
    assert "organization_suspended" in actions


async def test_get_organization_members_and_usage(client, db_session, register_payload):
    token, user, org_id = await _make_admin_and_org(client, db_session, register_payload)

    members = await client.get(f"/admin/organizations/{org_id}/members", headers=_auth_header(token))
    assert members.status_code == 200
    assert any(m["email"] == user.email for m in members.json())

    usage = await client.get(f"/admin/organizations/{org_id}/usage", headers=_auth_header(token))
    assert usage.status_code == 200
    assert "documents" in usage.json()


async def test_delete_organization_requires_superadmin(client, db_session, register_payload):
    token, _, org_id = await _make_admin_and_org(client, db_session, register_payload)  # admin, not superadmin
    response = await client.delete(f"/admin/organizations/{org_id}", headers=_auth_header(token))
    assert response.status_code == 403


async def test_organization_billing_returns_real_free_subscription(client, db_session, register_payload):
    token, _, org_id = await _make_admin_and_org(client, db_session, register_payload)
    response = await client.get(f"/admin/organizations/{org_id}/billing", headers=_auth_header(token))
    assert response.status_code == 200
    assert response.json()["status"] == "active"
