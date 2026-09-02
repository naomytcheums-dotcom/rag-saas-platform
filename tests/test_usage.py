"""
Partie 1.3.8 -- per-organization usage tracking. Fast SQLite suite, same
tier as tests/test_quotas.py.
"""

import datetime as dt
import uuid

from sqlalchemy import select

from api.models.organization import OrganizationMember, OrganizationRole
from api.models.organization_quota import OrganizationQuota
from api.models.organization_usage import OrganizationUsage
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


async def _add_member(db_session, org_id, user_id, role: OrganizationRole, invited_by=None):
    db_session.add(OrganizationMember(organization_id=org_id, user_id=user_id, role=role, invited_by=invited_by))
    await db_session.commit()


# ---------------------------------------------------- recording (item 3) --

async def test_creating_a_workspace_records_usage(client, db_session, register_payload):
    owner_token, owner = await _register(client, db_session, register_payload["email"], register_payload["password"])
    org = await _create_org(client, owner_token, "Acme")

    created = await client.post(f"/organizations/{org['id']}/workspaces", json={"name": "First"}, headers=_auth_header(owner_token))
    assert created.status_code == 201

    usage = await client.get(f"/organizations/{org['id']}/usage?metric=workspaces_created", headers=_auth_header(owner_token))
    assert usage.status_code == 200
    assert usage.json()["total"] == 1

    details = await client.get(f"/organizations/{org['id']}/usage/details?metric=workspaces_created", headers=_auth_header(owner_token))
    rows = details.json()["items"]
    assert len(rows) == 1
    assert rows[0]["value"] == 1
    assert rows[0]["user_id"] == str(owner.id)
    assert uuid.UUID(rows[0]["metadata"]["workspace_id"]) == uuid.UUID(created.json()["id"])


async def test_creating_a_team_records_usage(client, db_session, register_payload):
    owner_token, owner = await _register(client, db_session, register_payload["email"], register_payload["password"])
    org = await _create_org(client, owner_token, "Acme")

    created = await client.post(f"/organizations/{org['id']}/teams", json={"name": "Core"}, headers=_auth_header(owner_token))
    assert created.status_code == 201

    usage = await client.get(f"/organizations/{org['id']}/usage?metric=teams_created", headers=_auth_header(owner_token))
    assert usage.json()["total"] == 1


async def test_inviting_an_existing_member_records_usage(client, db_session, register_payload, monkeypatch):
    monkeypatch.setattr("api.routers.organization_members.send_organization_member_added_email", lambda *a: None)

    owner_token, owner = await _register(client, db_session, register_payload["email"], register_payload["password"])
    org = await _create_org(client, owner_token, "Acme")
    await _register(client, db_session, "invitee@example.com")

    invited = await client.post(
        f"/organizations/{org['id']}/members/invite", json={"email": "invitee@example.com"}, headers=_auth_header(owner_token),
    )
    assert invited.status_code == 201

    usage = await client.get(f"/organizations/{org['id']}/usage?metric=members_invited", headers=_auth_header(owner_token))
    assert usage.json()["total"] == 1


async def test_accepting_an_email_invitation_records_usage(client, db_session, register_payload, monkeypatch):
    captured = {}
    monkeypatch.setattr("api.routers.invitations.send_organization_invitation_email", lambda *a: captured.update(link=a[3]))
    monkeypatch.setattr("api.routers.invitations.send_organization_member_added_email", lambda *a: None)

    owner_token, owner = await _register(client, db_session, register_payload["email"], register_payload["password"])
    org = await _create_org(client, owner_token, "Acme")
    await _register(client, db_session, "linkjoiner@example.com")

    await client.post(
        f"/organizations/{org['id']}/invitations", json={"email": "linkjoiner@example.com", "role": "member"},
        headers=_auth_header(owner_token),
    )
    token = captured["link"].split("token=")[1]
    accepted = await client.post("/invitations/accept", json={"token": token})
    assert accepted.status_code == 200

    usage = await client.get(f"/organizations/{org['id']}/usage?metric=members_invited", headers=_auth_header(owner_token))
    assert usage.json()["total"] == 1


async def test_exceeding_a_quota_records_a_quota_exceeded_event(client, db_session, register_payload):
    owner_token, owner = await _register(client, db_session, register_payload["email"], register_payload["password"])
    org = await _create_org(client, owner_token, "Acme")
    org_id = uuid.UUID(org["id"])

    quota = await db_session.scalar(select(OrganizationQuota).where(OrganizationQuota.organization_id == org_id))
    quota.max_workspaces = 0
    await db_session.commit()

    blocked = await client.post(f"/organizations/{org['id']}/workspaces", json={"name": "Nope"}, headers=_auth_header(owner_token))
    assert blocked.status_code == 402

    usage = await client.get(f"/organizations/{org['id']}/usage?metric=quota_exceeded", headers=_auth_header(owner_token))
    assert usage.json()["total"] == 1

    details = await client.get(f"/organizations/{org['id']}/usage/details?metric=quota_exceeded", headers=_auth_header(owner_token))
    assert details.json()["items"][0]["metadata"]["resource_type"] == "workspaces"


# --------------------------------------------------- aggregation (item 3) --

async def test_usage_summary_aggregates_multiple_events_on_the_same_day(client, db_session, register_payload):
    owner_token, owner = await _register(client, db_session, register_payload["email"], register_payload["password"])
    org = await _create_org(client, owner_token, "Acme")

    await client.post(f"/organizations/{org['id']}/workspaces", json={"name": "First"}, headers=_auth_header(owner_token))
    await client.post(f"/organizations/{org['id']}/workspaces", json={"name": "Second"}, headers=_auth_header(owner_token))

    summary = await client.get(f"/organizations/{org['id']}/usage", headers=_auth_header(owner_token))
    body = summary.json()
    assert body["total_by_metric"]["workspaces_created"] == 2
    assert len(body["by_day"]) == 1  # both events recorded on the same day, one aggregate row
    assert body["by_day"][0]["metrics"]["workspaces_created"] == 2


async def test_get_usage_for_a_never_recorded_metric_returns_zero(client, db_session, register_payload):
    owner_token, owner = await _register(client, db_session, register_payload["email"], register_payload["password"])
    org = await _create_org(client, owner_token, "Acme")

    usage = await client.get(f"/organizations/{org['id']}/usage?metric=documents_processed", headers=_auth_header(owner_token))
    assert usage.status_code == 200
    assert usage.json()["total"] == 0


# -------------------------------------------------------- filtering by date --

async def test_usage_is_filtered_by_date_range(client, db_session, register_payload):
    owner_token, owner = await _register(client, db_session, register_payload["email"], register_payload["password"])
    org = await _create_org(client, owner_token, "Acme")
    org_id = uuid.UUID(org["id"])

    today = dt.datetime.now(dt.timezone.utc).date()
    yesterday = today - dt.timedelta(days=1)
    db_session.add(OrganizationUsage(organization_id=org_id, date=yesterday, metric="workspaces_created", value=5))
    db_session.add(OrganizationUsage(organization_id=org_id, date=today, metric="workspaces_created", value=3))
    await db_session.commit()

    only_today = await client.get(
        f"/organizations/{org['id']}/usage?metric=workspaces_created&start_date={today.isoformat()}",
        headers=_auth_header(owner_token),
    )
    assert only_today.json()["total"] == 3

    both_days = await client.get(
        f"/organizations/{org['id']}/usage?metric=workspaces_created&start_date={yesterday.isoformat()}&end_date={today.isoformat()}",
        headers=_auth_header(owner_token),
    )
    assert both_days.json()["total"] == 8

    only_yesterday = await client.get(
        f"/organizations/{org['id']}/usage?metric=workspaces_created&start_date={yesterday.isoformat()}&end_date={yesterday.isoformat()}",
        headers=_auth_header(owner_token),
    )
    assert only_yesterday.json()["total"] == 5


# ------------------------------------------------------------- pagination --

async def test_usage_details_are_paginated(client, db_session, register_payload):
    owner_token, owner = await _register(client, db_session, register_payload["email"], register_payload["password"])
    org = await _create_org(client, owner_token, "Acme")

    for name in ("A", "B", "C"):
        await client.post(f"/organizations/{org['id']}/workspaces", json={"name": name}, headers=_auth_header(owner_token))

    page = await client.get(f"/organizations/{org['id']}/usage/details?limit=2&offset=0", headers=_auth_header(owner_token))
    body = page.json()
    assert body["total"] == 3
    assert len(body["items"]) == 2
    assert body["limit"] == 2
    assert body["offset"] == 0

    second_page = await client.get(f"/organizations/{org['id']}/usage/details?limit=2&offset=2", headers=_auth_header(owner_token))
    assert len(second_page.json()["items"]) == 1


# ----------------------------------------------------------------- export --

async def test_export_as_json(client, db_session, register_payload):
    owner_token, owner = await _register(client, db_session, register_payload["email"], register_payload["password"])
    org = await _create_org(client, owner_token, "Acme")
    await client.post(f"/organizations/{org['id']}/workspaces", json={"name": "First"}, headers=_auth_header(owner_token))

    export = await client.get(f"/organizations/{org['id']}/usage/export", headers=_auth_header(owner_token))
    assert export.status_code == 200
    assert export.headers["content-type"].startswith("application/json")
    assert "attachment" in export.headers["content-disposition"]
    body = export.json()
    assert any(row["metric"] == "workspaces_created" and row["value"] == 1 for row in body["usage"])


async def test_export_as_csv(client, db_session, register_payload):
    owner_token, owner = await _register(client, db_session, register_payload["email"], register_payload["password"])
    org = await _create_org(client, owner_token, "Acme")
    await client.post(f"/organizations/{org['id']}/workspaces", json={"name": "First"}, headers=_auth_header(owner_token))

    export = await client.get(f"/organizations/{org['id']}/usage/export?format=csv", headers=_auth_header(owner_token))
    assert export.status_code == 200
    assert export.headers["content-type"].startswith("text/csv")
    assert "workspaces_created" in export.text
    assert export.text.startswith("date,metric,value")


# ------------------------------------------------------------ permissions --

async def test_manager_cannot_view_usage(client, db_session, register_payload):
    owner_token, owner = await _register(client, db_session, register_payload["email"], register_payload["password"])
    org = await _create_org(client, owner_token, "Acme")

    manager_token, manager = await _register(client, db_session, "usagemanager@example.com")
    await _add_member(db_session, uuid.UUID(org["id"]), manager.id, OrganizationRole.manager, invited_by=owner.id)

    response = await client.get(f"/organizations/{org['id']}/usage", headers=_auth_header(manager_token))
    assert response.status_code == 403


async def test_a_member_of_another_organization_cannot_view_this_organizations_usage(client, db_session, register_payload):
    owner_token, owner = await _register(client, db_session, register_payload["email"], register_payload["password"])
    org = await _create_org(client, owner_token, "Acme")

    # Registration auto-creates its own default organization (Etape
    # 1.2.2) -- outsider is Owner there, just not a member of `org`.
    outsider_token, outsider = await _register(client, db_session, "outsider@example.com")

    response = await client.get(f"/organizations/{org['id']}/usage", headers=_auth_header(outsider_token))
    assert response.status_code == 404  # anti-enumeration, same as require_org_member elsewhere

    details = await client.get(f"/organizations/{org['id']}/usage/details", headers=_auth_header(outsider_token))
    assert details.status_code == 404

    export = await client.get(f"/organizations/{org['id']}/usage/export", headers=_auth_header(outsider_token))
    assert export.status_code == 404


async def test_admin_can_view_usage(client, db_session, register_payload):
    owner_token, owner = await _register(client, db_session, register_payload["email"], register_payload["password"])
    org = await _create_org(client, owner_token, "Acme")

    admin_token, admin = await _register(client, db_session, "usageadmin@example.com")
    await _add_member(db_session, uuid.UUID(org["id"]), admin.id, OrganizationRole.admin, invited_by=owner.id)

    response = await client.get(f"/organizations/{org['id']}/usage", headers=_auth_header(admin_token))
    assert response.status_code == 200
