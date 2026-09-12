"""Partie 20 -- technical metrics: thin, honest re-exposure of
Prometheus/app_metrics for performance/errors (platform-wide, not
per-org -- see api/services/analytics.py's own docstring), and the
real bridge from Evaluation Lab's token/cost tracking for llm-usage."""

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


async def test_performance_and_errors_require_admin(client, db_session, register_payload):
    from api.models.organization import OrganizationMember, OrganizationRole

    owner_token, owner = await _register(client, db_session, register_payload["email"], register_payload["password"])
    org = await _create_org(client, owner_token, "Acme")
    member_token, member = await _register(client, db_session, "tech_member@example.com")
    db_session.add(OrganizationMember(organization_id=uuid.UUID(org["id"]), user_id=member.id, role=OrganizationRole.member, invited_by=owner.id))
    await db_session.commit()

    response = await client.get(f"/organizations/{org['id']}/analytics/technical/performance", headers=_auth_header(member_token))
    assert response.status_code == 403


async def test_performance_returns_the_real_prometheus_summary(client, db_session, register_payload):
    owner_token, _owner = await _register(client, db_session, register_payload["email"], register_payload["password"])
    org = await _create_org(client, owner_token, "Acme")

    response = await client.get(f"/organizations/{org['id']}/analytics/technical/performance", headers=_auth_header(owner_token))
    assert response.status_code == 200
    body = response.json()
    assert "request_duration_observation_count" in body
    assert "http_requests_total_samples" in body


async def test_llm_usage_is_honestly_empty_with_no_evaluation_runs(client, db_session, register_payload):
    owner_token, _owner = await _register(client, db_session, register_payload["email"], register_payload["password"])
    org = await _create_org(client, owner_token, "Acme")

    response = await client.get(f"/organizations/{org['id']}/analytics/technical/llm-usage", headers=_auth_header(owner_token))
    assert response.status_code == 200
    body = response.json()
    assert body["request_count"] == 0
    assert body["total_tokens"] == 0
    assert body["scope"] == "evaluation_lab_runs_only"


async def test_llm_usage_aggregates_real_evaluation_result_metrics(client, db_session, register_payload):
    from api.models.evaluation import EvaluationDataset, EvaluationQuestion, EvaluationResult

    owner_token, _owner = await _register(client, db_session, register_payload["email"], register_payload["password"])
    org = await _create_org(client, owner_token, "Acme")
    org_id = uuid.UUID(org["id"])

    dataset = EvaluationDataset(organization_id=org_id, name="LLM usage test dataset")
    db_session.add(dataset)
    await db_session.flush()
    question = EvaluationQuestion(dataset_id=dataset.id, question="What is 2+2?")
    db_session.add(question)
    await db_session.flush()
    db_session.add(EvaluationResult(
        question_id=question.id, model_config_json={"model": "test"}, retrieved_documents=[], retrieved_chunks=[],
        actual_answer="4", metrics={"total_tokens": 150, "cost_per_request": 0.002}, latency_ms=200,
    ))
    await db_session.commit()

    response = await client.get(f"/organizations/{org['id']}/analytics/technical/llm-usage", headers=_auth_header(owner_token))
    body = response.json()
    assert body["request_count"] == 1
    assert body["total_tokens"] == 150
    assert abs(body["total_cost"] - 0.002) < 1e-9
