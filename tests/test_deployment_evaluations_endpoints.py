"""Partie 7.3.8 -- auto-eval before deployment endpoints. Fast SQLite suite."""

from unittest.mock import patch

from sqlalchemy import select

from api.models.user import User


def _auth_header(access_token: str) -> dict:
    return {"Authorization": f"Bearer {access_token}"}


async def _register(client, db_session, email: str, password: str = "correct-horse-battery-staple"):
    payload = {"email": email, "password": password, "accept_terms": True}
    access_token = (await client.post("/auth/register", json=payload)).json()["access_token"]
    user = await db_session.scalar(select(User).where(User.email == email))
    return access_token, user


async def _make_org_agent_and_dataset(client, db_session, register_payload, name):
    owner_token, _owner = await _register(client, db_session, register_payload["email"], register_payload["password"])
    org_id = (await client.post("/organizations", json={"name": name}, headers=_auth_header(owner_token))).json()["id"]
    agent = (await client.post(
        f"/organizations/{org_id}/agents", json={"name": "Bot", "system_prompt": "You are helpful."}, headers=_auth_header(owner_token),
    )).json()
    dataset = (await client.post(f"/organizations/{org_id}/datasets", json={"name": "D"}, headers=_auth_header(owner_token))).json()
    return owner_token, agent, dataset


async def test_create_deployment_evaluation_endpoint_works(client, db_session, register_payload):
    """Validation criterion: la création d'évaluation fonctionne."""
    owner_token, agent, dataset = await _make_org_agent_and_dataset(client, db_session, register_payload, "Deploy Eval Endpoint Org")
    with patch("api.routers.deployment_evaluations.schedule_deployment_evaluation_processing"):
        response = await client.post(
            f"/agents/{agent['id']}/deploy/evaluate", json={"dataset_id": dataset["id"], "version": "v1.0.0"},
            headers=_auth_header(owner_token),
        )
    assert response.status_code == 201
    assert response.json()["status"] == "pending"


async def test_deploy_agent_endpoint_is_honestly_blocked_with_no_real_evaluation(client, db_session, register_payload):
    """Validation criterion: robustesse."""
    owner_token, agent, _dataset = await _make_org_agent_and_dataset(client, db_session, register_payload, "Deploy Agent Endpoint Org")
    response = await client.post(f"/agents/{agent['id']}/deploy", headers=_auth_header(owner_token))
    assert response.status_code == 200
    assert response.json()["deployed"] is False


async def test_create_deployment_evaluation_endpoint_respects_permissions(client, db_session, register_payload):
    """Validation criterion: les permissions sont respectées."""
    owner_token, agent, dataset = await _make_org_agent_and_dataset(client, db_session, register_payload, "Deploy Eval Perms Org")
    other_token, _other = await _register(client, db_session, "non-member-deploy-eval@example.com")

    response = await client.post(
        f"/agents/{agent['id']}/deploy/evaluate", json={"dataset_id": dataset["id"], "version": "v1.0.0"},
        headers=_auth_header(other_token),
    )
    assert response.status_code == 404
