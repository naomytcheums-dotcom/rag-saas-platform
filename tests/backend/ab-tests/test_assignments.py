"""Partie 21 -- real, persisted variant assignments
(ABTestAssignment) and the deterministic, sticky bucketing they
record. Real, direct tests of api/services/ab_tests.py's own
get_ab_test_variant (pure, sync, unchanged since Partie 7.3.10) and
assign_ab_test_variant/get_user_variant (new, Partie 21) -- there is
no HTTP endpoint for bucketing itself (deliberate, see
api/routers/ab_tests.py's own top docstring), only for listing the
resulting assignments."""

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


async def _make_org(client, db_session, register_payload, name):
    owner_token, _owner = await _register(client, db_session, register_payload["email"], register_payload["password"])
    org_id = (await client.post("/organizations", json={"name": name}, headers=_auth_header(owner_token))).json()["id"]
    return owner_token, org_id


async def test_bucketing_is_deterministic_for_the_same_request_id(client, db_session, register_payload):
    from api.services.ab_tests import get_ab_test, get_ab_test_variant

    owner_token, org_id = await _make_org(client, db_session, register_payload, "Deterministic Org")
    created = (await client.post(f"/organizations/{org_id}/ab-tests", json={"name": "T", "variant_a": {}, "variant_b": {}}, headers=_auth_header(owner_token))).json()
    await client.post(f"/ab-tests/{created['id']}/start", headers=_auth_header(owner_token))
    test = await get_ab_test(db_session, uuid.UUID(created["id"]))

    first = get_ab_test_variant(test, "user-42")
    second = get_ab_test_variant(test, "user-42")
    assert first == second


async def test_bucketing_respects_traffic_split(client, db_session, register_payload):
    from api.services.ab_tests import get_ab_test, get_ab_test_variant

    owner_token, org_id = await _make_org(client, db_session, register_payload, "Split Org")
    created = (await client.post(
        f"/organizations/{org_id}/ab-tests", json={"name": "T", "variant_a": {}, "variant_b": {}, "traffic_split": 0}, headers=_auth_header(owner_token),
    )).json()
    await client.post(f"/ab-tests/{created['id']}/start", headers=_auth_header(owner_token))
    test = await get_ab_test(db_session, uuid.UUID(created["id"]))

    # traffic_split=0 means NO real request should ever bucket into "a"
    variants = {get_ab_test_variant(test, f"user-{i}") for i in range(50)}
    assert variants == {"b"}


async def test_non_running_test_always_returns_variant_a(client, db_session, register_payload):
    from api.services.ab_tests import get_ab_test, get_ab_test_variant

    owner_token, org_id = await _make_org(client, db_session, register_payload, "Draft Org")
    created = (await client.post(f"/organizations/{org_id}/ab-tests", json={"name": "T", "variant_a": {}, "variant_b": {}, "traffic_split": 0}, headers=_auth_header(owner_token))).json()
    test = await get_ab_test(db_session, uuid.UUID(created["id"]))  # never started -- still "draft"

    assert get_ab_test_variant(test, "any-user") == "a"


async def test_assign_ab_test_variant_persists_a_real_assignment(client, db_session, register_payload):
    from api.services.ab_tests import assign_ab_test_variant, get_ab_test, get_user_variant

    owner_token, org_id = await _make_org(client, db_session, register_payload, "Assignment Org")
    created = (await client.post(f"/organizations/{org_id}/ab-tests", json={"name": "T", "variant_a": {}, "variant_b": {}}, headers=_auth_header(owner_token))).json()
    await client.post(f"/ab-tests/{created['id']}/start", headers=_auth_header(owner_token))
    test_id = uuid.UUID(created["id"])

    assert await get_user_variant(db_session, test_id, "user-99") is None  # honestly nothing recorded yet

    test = await get_ab_test(db_session, test_id)
    variant = await assign_ab_test_variant(db_session, test, "user-99")
    await db_session.commit()

    recorded = await get_user_variant(db_session, test_id, "user-99")
    assert recorded == variant


async def test_calling_assign_ab_test_variant_twice_does_not_duplicate_the_assignment(client, db_session, register_payload):
    from api.models.evaluation import ABTestAssignment
    from api.services.ab_tests import assign_ab_test_variant, get_ab_test

    owner_token, org_id = await _make_org(client, db_session, register_payload, "No Dup Org")
    created = (await client.post(f"/organizations/{org_id}/ab-tests", json={"name": "T", "variant_a": {}, "variant_b": {}}, headers=_auth_header(owner_token))).json()
    await client.post(f"/ab-tests/{created['id']}/start", headers=_auth_header(owner_token))
    test_id = uuid.UUID(created["id"])
    test = await get_ab_test(db_session, test_id)

    await assign_ab_test_variant(db_session, test, "user-7")
    await assign_ab_test_variant(db_session, test, "user-7")
    await db_session.commit()

    rows = (await db_session.scalars(select(ABTestAssignment).where(ABTestAssignment.ab_test_id == test_id, ABTestAssignment.request_id == "user-7"))).all()
    assert len(rows) == 1


async def test_assignments_endpoint_lists_real_recorded_assignments(client, db_session, register_payload):
    from api.services.ab_tests import assign_ab_test_variant, get_ab_test

    owner_token, org_id = await _make_org(client, db_session, register_payload, "List Assignments Org")
    created = (await client.post(f"/organizations/{org_id}/ab-tests", json={"name": "T", "variant_a": {}, "variant_b": {}}, headers=_auth_header(owner_token))).json()
    await client.post(f"/ab-tests/{created['id']}/start", headers=_auth_header(owner_token))
    test_id = uuid.UUID(created["id"])
    test = await get_ab_test(db_session, test_id)
    await assign_ab_test_variant(db_session, test, "user-a")
    await assign_ab_test_variant(db_session, test, "user-b")
    await db_session.commit()

    response = await client.get(f"/ab-tests/{created['id']}/assignments", headers=_auth_header(owner_token))
    assert response.status_code == 200
    body = response.json()
    assert body["total"] == 2
    assert {row["request_id"] for row in body["items"]} == {"user-a", "user-b"}


async def test_member_cannot_list_assignments(client, db_session, register_payload):
    from api.models.organization import OrganizationMember, OrganizationRole

    owner_token, owner = await _register(client, db_session, register_payload["email"], register_payload["password"])
    org_id = (await client.post("/organizations", json={"name": "Assignment Perms Org"}, headers=_auth_header(owner_token))).json()["id"]
    member_token, member = await _register(client, db_session, "assignment_member@example.com")
    db_session.add(OrganizationMember(organization_id=uuid.UUID(org_id), user_id=member.id, role=OrganizationRole.member, invited_by=owner.id))
    await db_session.commit()

    test = (await client.post(f"/organizations/{org_id}/ab-tests", json={"name": "T", "variant_a": {}, "variant_b": {}}, headers=_auth_header(owner_token))).json()

    response = await client.get(f"/ab-tests/{test['id']}/assignments", headers=_auth_header(member_token))
    assert response.status_code == 403
