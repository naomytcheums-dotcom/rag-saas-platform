"""Partie 20 -- product metrics (usage/adoption/engagement/funnels),
per organization, built on the new AnalyticsEvent table."""

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


async def test_adoption_is_empty_with_no_tracked_events(client, db_session, register_payload):
    owner_token, _owner = await _register(client, db_session, register_payload["email"], register_payload["password"])
    org = await _create_org(client, owner_token, "Acme")

    response = await client.get(f"/organizations/{org['id']}/analytics/product/adoption", headers=_auth_header(owner_token))
    assert response.status_code == 200
    assert response.json()["by_event_type"] == []


async def test_adoption_counts_real_events_and_distinct_users(client, db_session, register_payload):
    owner_token, _owner = await _register(client, db_session, register_payload["email"], register_payload["password"])
    org = await _create_org(client, owner_token, "Acme")
    await client.post(f"/organizations/{org['id']}/analytics/events", json={"event_type": "agent.created"}, headers=_auth_header(owner_token))
    await client.post(f"/organizations/{org['id']}/analytics/events", json={"event_type": "agent.created"}, headers=_auth_header(owner_token))

    response = await client.get(f"/organizations/{org['id']}/analytics/product/adoption", headers=_auth_header(owner_token))
    body = response.json()["by_event_type"]
    assert len(body) == 1
    assert body[0]["event_type"] == "agent.created"
    assert body[0]["event_count"] == 2
    assert body[0]["distinct_users"] == 1  # same owner both times


async def test_engagement_reports_daily_active_users(client, db_session, register_payload):
    owner_token, _owner = await _register(client, db_session, register_payload["email"], register_payload["password"])
    org = await _create_org(client, owner_token, "Acme")
    await client.post(f"/organizations/{org['id']}/analytics/events", json={"event_type": "conversation.created"}, headers=_auth_header(owner_token))

    response = await client.get(f"/organizations/{org['id']}/analytics/product/engagement", headers=_auth_header(owner_token))
    assert response.status_code == 200
    body = response.json()["daily_active_users"]
    assert len(body) == 1
    assert body[0]["active_users"] == 1


async def test_funnel_counts_distinct_users_per_step(client, db_session, register_payload):
    owner_token, _owner = await _register(client, db_session, register_payload["email"], register_payload["password"])
    org = await _create_org(client, owner_token, "Acme")
    await client.post(f"/organizations/{org['id']}/analytics/events", json={"event_type": "signup"}, headers=_auth_header(owner_token))
    await client.post(f"/organizations/{org['id']}/analytics/events", json={"event_type": "document.uploaded"}, headers=_auth_header(owner_token))
    # "conversation.created" deliberately never tracked -- the funnel must honestly show 0, not fabricate a number

    response = await client.get(
        f"/organizations/{org['id']}/analytics/product/funnels?steps=signup,document.uploaded,conversation.created",
        headers=_auth_header(owner_token),
    )
    assert response.status_code == 200
    funnel = {row["step"]: row["users"] for row in response.json()["funnel"]}
    assert funnel["signup"] == 1
    assert funnel["document.uploaded"] == 1
    assert funnel["conversation.created"] == 0


async def test_usage_reuses_the_real_organization_usage_ledger(client, db_session, register_payload):
    from api.security.usage import record_usage

    owner_token, _owner = await _register(client, db_session, register_payload["email"], register_payload["password"])
    org = await _create_org(client, owner_token, "Acme")
    await record_usage(db_session, uuid.UUID(org["id"]), "workspace_created", 3)
    await db_session.commit()

    response = await client.get(f"/organizations/{org['id']}/analytics/product/usage", headers=_auth_header(owner_token))
    assert response.status_code == 200
    assert response.json()["by_metric"].get("workspace_created") == 3
