"""Partie 7.3.10 -- production A/B testing endpoints. Fast SQLite suite."""

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


async def test_create_ab_test_endpoint_works(client, db_session, register_payload):
    """Validation criterion: la création de test fonctionne."""
    owner_token, org_id = await _make_org(client, db_session, register_payload, "AB Test Endpoint Org")
    response = await client.post(
        f"/organizations/{org_id}/ab-tests",
        json={"name": "T", "variant_a": {"system_prompt": "A"}, "variant_b": {"system_prompt": "B"}},
        headers=_auth_header(owner_token),
    )
    assert response.status_code == 201
    assert response.json()["status"] == "draft"


async def test_start_and_track_and_results_endpoints_work(client, db_session, register_payload):
    """Validation criterion: le démarrage et l'enregistrement des métriques fonctionnent."""
    owner_token, org_id = await _make_org(client, db_session, register_payload, "AB Test Flow Endpoint Org")
    test = (await client.post(
        f"/organizations/{org_id}/ab-tests", json={"name": "T", "variant_a": {}, "variant_b": {}}, headers=_auth_header(owner_token),
    )).json()

    start_response = await client.post(f"/ab-tests/{test['id']}/start", headers=_auth_header(owner_token))
    assert start_response.status_code == 200
    assert start_response.json()["status"] == "running"

    track_response = await client.post(
        f"/ab-tests/{test['id']}/track", json={"variant": "a", "metric": "conversion_rate", "value": 1.0},
        headers=_auth_header(owner_token),
    )
    assert track_response.status_code == 200

    results_response = await client.get(f"/ab-tests/{test['id']}/results", headers=_auth_header(owner_token))
    assert results_response.status_code == 200


async def test_choose_ab_test_winner_endpoint_works(client, db_session, register_payload):
    """Validation criterion: les résultats sont corrects."""
    owner_token, org_id = await _make_org(client, db_session, register_payload, "AB Test Winner Endpoint Org")
    test = (await client.post(
        f"/organizations/{org_id}/ab-tests", json={"name": "T", "variant_a": {}, "variant_b": {}}, headers=_auth_header(owner_token),
    )).json()

    response = await client.post(f"/ab-tests/{test['id']}/variants/choose", json={"variant": "b"}, headers=_auth_header(owner_token))
    assert response.status_code == 200
    assert response.json()["status"] == "completed"
    assert response.json()["metrics"]["winner"] == "b"


async def test_create_ab_test_endpoint_respects_permissions(client, db_session, register_payload):
    """Validation criterion: les permissions sont respectées."""
    owner_token, org_id = await _make_org(client, db_session, register_payload, "AB Test Perms Org")
    other_token, _other = await _register(client, db_session, "non-admin-ab-test@example.com")

    response = await client.post(
        f"/organizations/{org_id}/ab-tests", json={"name": "T", "variant_a": {}, "variant_b": {}}, headers=_auth_header(other_token),
    )
    assert response.status_code == 404


async def test_get_ab_test_endpoint_respects_permissions(client, db_session, register_payload):
    """Validation criterion: les permissions sont respectées."""
    owner_token, org_id = await _make_org(client, db_session, register_payload, "AB Test Get Perms Org")
    test = (await client.post(
        f"/organizations/{org_id}/ab-tests", json={"name": "T", "variant_a": {}, "variant_b": {}}, headers=_auth_header(owner_token),
    )).json()
    other_token, _other = await _register(client, db_session, "non-admin-ab-test-get@example.com")

    response = await client.get(f"/ab-tests/{test['id']}", headers=_auth_header(other_token))
    assert response.status_code == 404
