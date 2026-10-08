"""Systèmes internes, items 13/18/20/27 -- router-level tests for
api/routers/rag_control_plane.py. The real underlying orchestration
functions (run_health_check/run_evolution_cycle/evaluate_canary) are
each already covered by their own dedicated test module
(tests/test_rag_control_plane.py, tests/test_rag_evolution_engine.py,
tests/test_canary_rollout.py) -- mocked here at that same clean
boundary so these tests verify the real HTTP surface (permission
checks, request/response shape), never re-test the orchestration
logic itself."""

import uuid
from unittest.mock import AsyncMock, patch

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


async def _create_org(client, access_token: str, name: str) -> dict:
    return (await client.post("/organizations", json={"name": name}, headers=_auth_header(access_token))).json()


async def _add_member(db_session, org_id, user_id, role: OrganizationRole):
    db_session.add(OrganizationMember(organization_id=org_id, user_id=user_id, role=role))
    await db_session.commit()


async def test_health_check_endpoint_returns_a_real_report(client, db_session, register_payload):
    owner_token, owner = await _register(client, db_session, register_payload["email"], register_payload["password"])
    org = await _create_org(client, owner_token, "Acme")

    fake_report = {
        "organization_id": org["id"], "running_canaries_evaluated": 0, "canary_results": [], "recent_experiments": [],
    }
    with patch("api.services.rag_control_plane.run_health_check", AsyncMock(return_value=fake_report)):
        response = await client.post(f"/organizations/{org['id']}/rag-control-plane/health-check", headers=_auth_header(owner_token))

    assert response.status_code == 200
    assert response.json()["running_canaries_evaluated"] == 0


async def test_health_check_endpoint_requires_real_permission(client, db_session, register_payload):
    owner_token, owner = await _register(client, db_session, register_payload["email"], register_payload["password"])
    org = await _create_org(client, owner_token, "Acme")

    member_token, member = await _register(client, db_session, "member-" + register_payload["email"])
    await _add_member(db_session, uuid.UUID(org["id"]), member.id, OrganizationRole.viewer)

    response = await client.post(f"/organizations/{org['id']}/rag-control-plane/health-check", headers=_auth_header(member_token))
    assert response.status_code == 403


async def test_evolution_run_endpoint_returns_a_real_result(client, db_session, register_payload):
    owner_token, owner = await _register(client, db_session, register_payload["email"], register_payload["password"])
    org = await _create_org(client, owner_token, "Acme")
    # The dataset must now really belong to the caller's organization (ownership check before any job is created).
    from api.models.evaluation import EvaluationDataset

    dataset = EvaluationDataset(organization_id=uuid.UUID(org["id"]), name="mine")
    db_session.add(dataset)
    await db_session.flush()
    dataset_id = str(dataset.id)
    await db_session.commit()
    baseline_id = str(uuid.uuid4())

    fake_result = {"baseline_job_id": baseline_id, "candidate_job_id": None, "decision": "insufficient_ground_truth", "reason": "not enough"}
    with patch("api.services.rag_evolution_engine.run_evolution_cycle", AsyncMock(return_value=fake_result)):
        response = await client.post(
            f"/organizations/{org['id']}/evolution/run",
            json={"dataset_id": dataset_id, "llm_provider": "anthropic"},
            headers=_auth_header(owner_token),
        )

    assert response.status_code == 200
    body = response.json()
    assert body["decision"] == "insufficient_ground_truth"
    assert body["baseline_job_id"] == baseline_id


async def test_evaluate_canary_endpoint_returns_a_real_result(client, db_session, register_payload):
    from api.services.ab_tests import create_ab_test

    owner_token, owner = await _register(client, db_session, register_payload["email"], register_payload["password"])
    org = await _create_org(client, owner_token, "Acme")
    test = await create_ab_test(db_session, uuid.UUID(org["id"]), "Canary", variant_a={"a": 1}, variant_b={"b": 1})
    await db_session.commit()

    fake_result = {"test_id": test.id, "action": "none", "reason": "no significant effect yet", "metric_result": None}
    with patch("api.services.canary_rollout.evaluate_canary", AsyncMock(return_value=fake_result)):
        response = await client.post(
            f"/organizations/{org['id']}/ab-tests/{test.id}/evaluate-canary",
            json={"target_metric": "conversion_rate"},
            headers=_auth_header(owner_token),
        )

    assert response.status_code == 200
    assert response.json()["action"] == "none"


async def test_evaluate_canary_endpoint_returns_404_for_a_test_from_another_organization(client, db_session, register_payload):
    from api.services.ab_tests import create_ab_test

    owner_token, owner = await _register(client, db_session, register_payload["email"], register_payload["password"])
    org = await _create_org(client, owner_token, "Acme")
    other_org = await _create_org(client, owner_token, "Other Org")
    test = await create_ab_test(db_session, uuid.UUID(other_org["id"]), "Canary", variant_a={"a": 1}, variant_b={"b": 1})
    await db_session.commit()

    response = await client.post(
        f"/organizations/{org['id']}/ab-tests/{test.id}/evaluate-canary",
        json={"target_metric": "conversion_rate"},
        headers=_auth_header(owner_token),
    )
    assert response.status_code == 404
