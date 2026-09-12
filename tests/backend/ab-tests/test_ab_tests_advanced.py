"""Partie 21 -- the real gaps this part added to the already-mature
Partie 7.3.10 A/B testing system: test_type/target_metric/
min_sample_size/confidence_level fields, update/delete/resume, and the
Member+/Admin+ access split. Base create/start/track/results coverage
already exists in tests/test_ab_tests_endpoints.py -- not re-tested here."""

import uuid

from sqlalchemy import select

from api.models.organization import OrganizationMember, OrganizationRole
from api.models.user import User


def _auth_header(access_token: str) -> dict:
    return {"Authorization": f"Bearer {access_token}"}


async def _register(client, db_session, email: str, password: str = "correct-horse-battery-staple"):
    payload = {"email": email, "password": password, "accept_terms": True}
    access_token = (await client.post("/auth/register", json=payload)).json()["access_token"]
    user = await db_session.scalar(select(User).where(User.email == email))
    return access_token, user


async def _make_org(client, db_session, register_payload, name):
    owner_token, owner = await _register(client, db_session, register_payload["email"], register_payload["password"])
    org_id = (await client.post("/organizations", json={"name": name}, headers=_auth_header(owner_token))).json()["id"]
    return owner_token, owner, org_id


async def test_create_with_test_type_and_target_metric(client, db_session, register_payload):
    owner_token, _owner, org_id = await _make_org(client, db_session, register_payload, "Config Org")
    response = await client.post(
        f"/organizations/{org_id}/ab-tests",
        json={
            "name": "Prompt test", "variant_a": {"prompt": "A"}, "variant_b": {"prompt": "B"},
            "test_type": "prompt", "target_metric": "conversion_rate", "min_sample_size": 50, "confidence_level": 0.90,
        },
        headers=_auth_header(owner_token),
    )
    assert response.status_code == 201
    body = response.json()
    assert body["test_type"] == "prompt"
    assert body["target_metric"] == "conversion_rate"
    assert body["min_sample_size"] == 50
    assert body["confidence_level"] == 0.90


async def test_create_rejects_an_unknown_target_metric(client, db_session, register_payload):
    owner_token, _owner, org_id = await _make_org(client, db_session, register_payload, "Bad Metric Org")
    response = await client.post(
        f"/organizations/{org_id}/ab-tests",
        json={"name": "T", "variant_a": {}, "variant_b": {}, "target_metric": "not_a_real_metric"},
        headers=_auth_header(owner_token),
    )
    assert response.status_code == 400


async def test_defaults_come_from_real_settings(client, db_session, register_payload):
    owner_token, _owner, org_id = await _make_org(client, db_session, register_payload, "Defaults Org")
    response = await client.post(
        f"/organizations/{org_id}/ab-tests", json={"name": "T", "variant_a": {}, "variant_b": {}}, headers=_auth_header(owner_token),
    )
    body = response.json()
    assert body["min_sample_size"] == 100
    assert body["confidence_level"] == 0.95


async def test_update_changes_name_and_traffic_split(client, db_session, register_payload):
    owner_token, _owner, org_id = await _make_org(client, db_session, register_payload, "Update Org")
    test = (await client.post(f"/organizations/{org_id}/ab-tests", json={"name": "Old", "variant_a": {}, "variant_b": {}}, headers=_auth_header(owner_token))).json()

    response = await client.patch(f"/ab-tests/{test['id']}", json={"name": "New", "traffic_split": 70}, headers=_auth_header(owner_token))
    assert response.status_code == 200
    assert response.json()["name"] == "New"
    assert response.json()["traffic_split"] == 70


async def test_delete_removes_the_test(client, db_session, register_payload):
    owner_token, _owner, org_id = await _make_org(client, db_session, register_payload, "Delete Org")
    test = (await client.post(f"/organizations/{org_id}/ab-tests", json={"name": "T", "variant_a": {}, "variant_b": {}}, headers=_auth_header(owner_token))).json()

    deleted = await client.delete(f"/ab-tests/{test['id']}", headers=_auth_header(owner_token))
    assert deleted.status_code == 204

    refetched = await client.get(f"/ab-tests/{test['id']}", headers=_auth_header(owner_token))
    assert refetched.status_code == 404


async def test_resume_restarts_a_paused_test(client, db_session, register_payload):
    owner_token, _owner, org_id = await _make_org(client, db_session, register_payload, "Resume Org")
    test = (await client.post(f"/organizations/{org_id}/ab-tests", json={"name": "T", "variant_a": {}, "variant_b": {}}, headers=_auth_header(owner_token))).json()
    await client.post(f"/ab-tests/{test['id']}/start", headers=_auth_header(owner_token))
    await client.post(f"/ab-tests/{test['id']}/pause", headers=_auth_header(owner_token))

    response = await client.post(f"/ab-tests/{test['id']}/resume", headers=_auth_header(owner_token))
    assert response.status_code == 200
    assert response.json()["status"] == "running"


async def test_member_can_list_and_view_but_not_create_or_update(client, db_session, register_payload):
    owner_token, owner, org_id = await _make_org(client, db_session, register_payload, "Member Perms Org")
    member_token, member = await _register(client, db_session, "abtest_member@example.com")
    db_session.add(OrganizationMember(organization_id=uuid.UUID(org_id), user_id=member.id, role=OrganizationRole.member, invited_by=owner.id))
    await db_session.commit()

    test = (await client.post(f"/organizations/{org_id}/ab-tests", json={"name": "T", "variant_a": {}, "variant_b": {}}, headers=_auth_header(owner_token))).json()

    list_response = await client.get(f"/organizations/{org_id}/ab-tests", headers=_auth_header(member_token))
    assert list_response.status_code == 200

    get_response = await client.get(f"/ab-tests/{test['id']}", headers=_auth_header(member_token))
    assert get_response.status_code == 200

    update_response = await client.patch(f"/ab-tests/{test['id']}", json={"name": "Nope"}, headers=_auth_header(member_token))
    assert update_response.status_code == 403
