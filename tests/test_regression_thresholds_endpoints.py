"""Partie 7.3.9 -- regression threshold endpoints. Fast SQLite suite."""

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


async def test_set_regression_threshold_endpoint_works(client, db_session, register_payload):
    """Validation criterion: la création de seuil fonctionne."""
    owner_token, org_id = await _make_org(client, db_session, register_payload, "Threshold Endpoint Org")
    response = await client.post(
        f"/organizations/{org_id}/thresholds", json={"metric": "faithfulness", "threshold": 0.7, "severity": "high"},
        headers=_auth_header(owner_token),
    )
    assert response.status_code == 201
    assert response.json()["metric"] == "faithfulness"


async def test_check_regression_thresholds_endpoint_works(client, db_session, register_payload):
    """Validation criterion: la vérification fonctionne."""
    owner_token, org_id = await _make_org(client, db_session, register_payload, "Threshold Check Endpoint Org")
    await client.post(
        f"/organizations/{org_id}/thresholds", json={"metric": "faithfulness", "threshold": 0.7, "severity": "high"},
        headers=_auth_header(owner_token),
    )
    response = await client.post(
        f"/organizations/{org_id}/thresholds/check", json={"metrics": {"faithfulness": 0.3}}, headers=_auth_header(owner_token),
    )
    assert response.status_code == 200
    assert len(response.json()) == 1


async def test_update_regression_threshold_endpoint_works(client, db_session, register_payload):
    """Validation criterion: les modifications fonctionnent."""
    owner_token, org_id = await _make_org(client, db_session, register_payload, "Threshold Update Endpoint Org")
    created = (await client.post(
        f"/organizations/{org_id}/thresholds", json={"metric": "faithfulness", "threshold": 0.7, "severity": "high"},
        headers=_auth_header(owner_token),
    )).json()

    response = await client.patch(f"/thresholds/{created['id']}", json={"threshold": 0.9}, headers=_auth_header(owner_token))
    assert response.status_code == 200
    assert response.json()["threshold"] == 0.9


async def test_set_regression_threshold_endpoint_respects_permissions(client, db_session, register_payload):
    """Validation criterion: les permissions sont respectées."""
    owner_token, org_id = await _make_org(client, db_session, register_payload, "Threshold Perms Org")
    other_token, _other = await _register(client, db_session, "non-admin-threshold@example.com")

    response = await client.post(
        f"/organizations/{org_id}/thresholds", json={"metric": "faithfulness", "threshold": 0.7, "severity": "high"},
        headers=_auth_header(other_token),
    )
    assert response.status_code == 404
