"""Partie 21 -- the real, automatic, statistics-driven
POST /ab-tests/{id}/decide, distinct from the pre-existing manual
POST .../variants/choose (unchanged, still tested elsewhere)."""

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


async def _track(client, owner_token, test_id, variant, values, metric="conversion_rate"):
    for value in values:
        await client.post(f"/ab-tests/{test_id}/track", json={"variant": variant, "metric": metric, "value": value}, headers=_auth_header(owner_token))


async def test_decide_requires_a_target_metric(client, db_session, register_payload):
    owner_token, org_id = await _make_org(client, db_session, register_payload, "No Target Org")
    test = (await client.post(f"/organizations/{org_id}/ab-tests", json={"name": "T", "variant_a": {}, "variant_b": {}}, headers=_auth_header(owner_token))).json()
    await client.post(f"/ab-tests/{test['id']}/start", headers=_auth_header(owner_token))

    response = await client.post(f"/ab-tests/{test['id']}/decide", headers=_auth_header(owner_token))
    assert response.status_code == 400


async def test_decide_is_honestly_none_below_min_sample_size(client, db_session, register_payload):
    owner_token, org_id = await _make_org(client, db_session, register_payload, "Below Sample Org")
    test = (await client.post(
        f"/organizations/{org_id}/ab-tests",
        json={"name": "T", "variant_a": {}, "variant_b": {}, "target_metric": "conversion_rate", "min_sample_size": 10},
        headers=_auth_header(owner_token),
    )).json()
    await client.post(f"/ab-tests/{test['id']}/start", headers=_auth_header(owner_token))
    await _track(client, owner_token, test["id"], "a", [1.0, 1.0])
    await _track(client, owner_token, test["id"], "b", [5.0, 5.0])

    response = await client.post(f"/ab-tests/{test['id']}/decide", headers=_auth_header(owner_token))
    assert response.status_code == 200
    assert response.json()["winner"] == "none"
    assert response.json()["status"] == "running"  # not force-completed just because it wasn't ready to decide


async def test_decide_picks_the_higher_mean_for_a_higher_is_better_metric(client, db_session, register_payload):
    owner_token, org_id = await _make_org(client, db_session, register_payload, "Higher Better Org")
    test = (await client.post(
        f"/organizations/{org_id}/ab-tests",
        json={"name": "T", "variant_a": {}, "variant_b": {}, "target_metric": "conversion_rate", "min_sample_size": 3},
        headers=_auth_header(owner_token),
    )).json()
    await client.post(f"/ab-tests/{test['id']}/start", headers=_auth_header(owner_token))
    await _track(client, owner_token, test["id"], "a", [1.0, 1.0, 1.0])
    await _track(client, owner_token, test["id"], "b", [9.0, 9.0, 9.0])

    response = await client.post(f"/ab-tests/{test['id']}/decide", headers=_auth_header(owner_token))
    assert response.status_code == 200
    assert response.json()["winner"] == "b"  # b's real mean (9.0) is higher, conversion_rate is "higher is better"
    assert response.json()["status"] == "completed"


async def test_decide_picks_the_lower_mean_for_a_lower_is_better_metric(client, db_session, register_payload):
    owner_token, org_id = await _make_org(client, db_session, register_payload, "Lower Better Org")
    test = (await client.post(
        f"/organizations/{org_id}/ab-tests",
        json={"name": "T", "variant_a": {}, "variant_b": {}, "target_metric": "avg_response_time", "min_sample_size": 3},
        headers=_auth_header(owner_token),
    )).json()
    await client.post(f"/ab-tests/{test['id']}/start", headers=_auth_header(owner_token))
    await _track(client, owner_token, test["id"], "a", [100.0, 100.0, 100.0], metric="avg_response_time")
    await _track(client, owner_token, test["id"], "b", [900.0, 900.0, 900.0], metric="avg_response_time")

    response = await client.post(f"/ab-tests/{test['id']}/decide", headers=_auth_header(owner_token))
    assert response.json()["winner"] == "a"  # a's real mean (100ms) is LOWER, avg_response_time is "lower is better"


async def test_manual_choose_winner_is_unaffected_by_the_new_decide_endpoint(client, db_session, register_payload):
    """The pre-existing, real, human decision path -- unchanged."""
    owner_token, org_id = await _make_org(client, db_session, register_payload, "Manual Choice Org")
    test = (await client.post(f"/organizations/{org_id}/ab-tests", json={"name": "T", "variant_a": {}, "variant_b": {}}, headers=_auth_header(owner_token))).json()

    response = await client.post(f"/ab-tests/{test['id']}/variants/choose", json={"variant": "a"}, headers=_auth_header(owner_token))
    assert response.status_code == 200
    assert response.json()["metrics"]["winner"] == "a"
    assert response.json()["winner"] is None  # the NEW automatic-decision column stays untouched by the manual path


async def test_member_cannot_decide(client, db_session, register_payload):
    from api.models.organization import OrganizationMember, OrganizationRole
    import uuid

    owner_token, owner = await _register(client, db_session, register_payload["email"], register_payload["password"])
    org_id = (await client.post("/organizations", json={"name": "Decide Perms Org"}, headers=_auth_header(owner_token))).json()["id"]
    member_token, member = await _register(client, db_session, "decide_member@example.com")
    db_session.add(OrganizationMember(organization_id=uuid.UUID(org_id), user_id=member.id, role=OrganizationRole.member, invited_by=owner.id))
    await db_session.commit()

    test = (await client.post(
        f"/organizations/{org_id}/ab-tests", json={"name": "T", "variant_a": {}, "variant_b": {}, "target_metric": "conversion_rate"}, headers=_auth_header(owner_token),
    )).json()

    response = await client.post(f"/ab-tests/{test['id']}/decide", headers=_auth_header(member_token))
    assert response.status_code == 403
