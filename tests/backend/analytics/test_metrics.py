"""Partie 20 -- generic event tracking, metrics query, and export."""

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


async def test_track_event_is_recorded(client, db_session, register_payload):
    from api.models.analytics import AnalyticsEvent

    owner_token, _owner = await _register(client, db_session, register_payload["email"], register_payload["password"])
    org = await _create_org(client, owner_token, "Acme")

    response = await client.post(
        f"/organizations/{org['id']}/analytics/events", json={"event_type": "document.uploaded", "event_data": {"size": 1234}},
        headers=_auth_header(owner_token),
    )
    assert response.status_code == 201

    row = await db_session.scalar(select(AnalyticsEvent).where(AnalyticsEvent.organization_id == uuid.UUID(org["id"])))
    assert row is not None
    assert row.event_type == "document.uploaded"
    assert row.event_data == {"size": 1234}


async def test_query_metrics_filters_by_event_type(client, db_session, register_payload):
    owner_token, _owner = await _register(client, db_session, register_payload["email"], register_payload["password"])
    org = await _create_org(client, owner_token, "Acme")
    await client.post(f"/organizations/{org['id']}/analytics/events", json={"event_type": "document.uploaded"}, headers=_auth_header(owner_token))
    await client.post(f"/organizations/{org['id']}/analytics/events", json={"event_type": "conversation.created"}, headers=_auth_header(owner_token))

    response = await client.get(f"/organizations/{org['id']}/analytics/metrics/query?event_type=document.uploaded", headers=_auth_header(owner_token))
    assert response.status_code == 200
    body = response.json()
    assert len(body) == 1
    assert body[0]["event_type"] == "document.uploaded"


async def test_export_metrics_as_json_and_csv(client, db_session, register_payload):
    owner_token, _owner = await _register(client, db_session, register_payload["email"], register_payload["password"])
    org = await _create_org(client, owner_token, "Acme")
    await client.post(f"/organizations/{org['id']}/analytics/events", json={"event_type": "agent.created"}, headers=_auth_header(owner_token))

    json_response = await client.get(f"/organizations/{org['id']}/analytics/metrics/export?format=json", headers=_auth_header(owner_token))
    assert json_response.status_code == 200
    assert json_response.headers["content-type"].startswith("application/json")
    assert "attachment" in json_response.headers["content-disposition"]
    assert json_response.json()[0]["event_type"] == "agent.created"

    csv_response = await client.get(f"/organizations/{org['id']}/analytics/metrics/export?format=csv", headers=_auth_header(owner_token))
    assert csv_response.status_code == 200
    assert csv_response.headers["content-type"].startswith("text/csv")
    assert "agent.created" in csv_response.text


async def test_export_rejects_an_unknown_format(client, db_session, register_payload):
    owner_token, _owner = await _register(client, db_session, register_payload["email"], register_payload["password"])
    org = await _create_org(client, owner_token, "Acme")

    response = await client.get(f"/organizations/{org['id']}/analytics/metrics/export?format=xml", headers=_auth_header(owner_token))
    assert response.status_code == 400


async def test_member_cannot_be_blocked_from_tracking_or_reading(client, db_session, register_payload):
    """Member+ (not Admin+) is enough for events/metrics -- these are
    read/track actions, not configuration changes."""
    from api.models.organization import OrganizationMember, OrganizationRole

    owner_token, owner = await _register(client, db_session, register_payload["email"], register_payload["password"])
    org = await _create_org(client, owner_token, "Acme")
    member_token, member = await _register(client, db_session, "analytics_member@example.com")
    db_session.add(OrganizationMember(organization_id=uuid.UUID(org["id"]), user_id=member.id, role=OrganizationRole.member, invited_by=owner.id))
    await db_session.commit()

    response = await client.get(f"/organizations/{org['id']}/analytics/metrics", headers=_auth_header(member_token))
    assert response.status_code == 200


async def test_non_member_gets_404(client, db_session, register_payload):
    owner_token, _owner = await _register(client, db_session, register_payload["email"], register_payload["password"])
    org = await _create_org(client, owner_token, "Acme")
    outsider_token, _outsider = await _register(client, db_session, "analytics_outsider@example.com")

    response = await client.get(f"/organizations/{org['id']}/analytics/metrics", headers=_auth_header(outsider_token))
    assert response.status_code == 404
