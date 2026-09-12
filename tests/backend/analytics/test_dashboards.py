"""Partie 20 -- custom analytics dashboards (AnalyticsDashboard),
the one genuinely-new-model area (confirmed by audit: no existing
"dashboard" in this codebase is user-configurable)."""

import uuid

from sqlalchemy import select

from api.models.user import User


def _auth_header(access_token: str) -> dict:
    return {"Authorization": f"Bearer {access_token}"}


async def _register(client, db_session, email: str, password: str = "correct-horse-battery-staple"):
    payload = {"email": email, "password": password, "accept_terms": True}
    access_token = (await client.post("/auth/register", json=payload)).json()["access_token"]
    user = await db_session.scalar(select(User).where(User.email == email))
    return access_token, user


async def _create_org(client, access_token: str, name: str) -> dict:
    return (await client.post("/organizations", json={"name": name}, headers=_auth_header(access_token))).json()


async def test_create_and_list_dashboards(client, db_session, register_payload):
    owner_token, _owner = await _register(client, db_session, register_payload["email"], register_payload["password"])
    org = await _create_org(client, owner_token, "Acme")

    created = await client.post(
        f"/organizations/{org['id']}/analytics/dashboards",
        json={"name": "Growth", "widgets": [{"type": "chart", "metric": "signups"}], "is_default": True},
        headers=_auth_header(owner_token),
    )
    assert created.status_code == 201
    assert created.json()["is_default"] is True

    listed = await client.get(f"/organizations/{org['id']}/analytics/dashboards", headers=_auth_header(owner_token))
    assert listed.status_code == 200
    assert len(listed.json()) == 1


async def test_only_one_default_dashboard_at_a_time(client, db_session, register_payload):
    owner_token, _owner = await _register(client, db_session, register_payload["email"], register_payload["password"])
    org = await _create_org(client, owner_token, "Acme")

    first = await client.post(f"/organizations/{org['id']}/analytics/dashboards", json={"name": "A", "is_default": True}, headers=_auth_header(owner_token))
    second = await client.post(f"/organizations/{org['id']}/analytics/dashboards", json={"name": "B", "is_default": True}, headers=_auth_header(owner_token))
    assert second.json()["is_default"] is True

    refetched_first = await client.get(f"/organizations/{org['id']}/analytics/dashboards/{first.json()['id']}", headers=_auth_header(owner_token))
    assert refetched_first.json()["is_default"] is False


async def test_update_dashboard_widgets(client, db_session, register_payload):
    owner_token, _owner = await _register(client, db_session, register_payload["email"], register_payload["password"])
    org = await _create_org(client, owner_token, "Acme")
    created = await client.post(f"/organizations/{org['id']}/analytics/dashboards", json={"name": "Growth"}, headers=_auth_header(owner_token))

    response = await client.patch(
        f"/organizations/{org['id']}/analytics/dashboards/{created.json()['id']}",
        json={"widgets": [{"type": "table", "metric": "churn"}]}, headers=_auth_header(owner_token),
    )
    assert response.status_code == 200
    assert response.json()["widgets"] == [{"type": "table", "metric": "churn"}]


async def test_delete_dashboard(client, db_session, register_payload):
    owner_token, _owner = await _register(client, db_session, register_payload["email"], register_payload["password"])
    org = await _create_org(client, owner_token, "Acme")
    created = await client.post(f"/organizations/{org['id']}/analytics/dashboards", json={"name": "Temp"}, headers=_auth_header(owner_token))

    deleted = await client.delete(f"/organizations/{org['id']}/analytics/dashboards/{created.json()['id']}", headers=_auth_header(owner_token))
    assert deleted.status_code == 204

    refetched = await client.get(f"/organizations/{org['id']}/analytics/dashboards/{created.json()['id']}", headers=_auth_header(owner_token))
    assert refetched.status_code == 404


async def test_member_cannot_create_dashboard(client, db_session, register_payload):
    from api.models.organization import OrganizationMember, OrganizationRole

    owner_token, owner = await _register(client, db_session, register_payload["email"], register_payload["password"])
    org = await _create_org(client, owner_token, "Acme")
    member_token, member = await _register(client, db_session, "dash_member@example.com")
    db_session.add(OrganizationMember(organization_id=uuid.UUID(org["id"]), user_id=member.id, role=OrganizationRole.member, invited_by=owner.id))
    await db_session.commit()

    response = await client.post(f"/organizations/{org['id']}/analytics/dashboards", json={"name": "Nope"}, headers=_auth_header(member_token))
    assert response.status_code == 403


async def test_getting_a_dashboard_from_another_organization_is_a_real_404(client, db_session, register_payload):
    owner_token, _owner = await _register(client, db_session, register_payload["email"], register_payload["password"])
    org_a = await _create_org(client, owner_token, "Org A")
    org_b = await _create_org(client, owner_token, "Org B")
    created = await client.post(f"/organizations/{org_a['id']}/analytics/dashboards", json={"name": "A's dashboard"}, headers=_auth_header(owner_token))

    response = await client.get(f"/organizations/{org_b['id']}/analytics/dashboards/{created.json()['id']}", headers=_auth_header(owner_token))
    assert response.status_code == 404
