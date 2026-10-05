"""Hardening Mission, §13 -- organization-scoped Guardian routes. Before them,
every `/alerting/*` route was platform-admin-only and created rules with no
organization, so the per-organization RAG-quality metrics could not be
configured by any customer: the Guardian logic existed but was UNREACHABLE
through the API. Real DB session and real HTTP calls throughout."""

import datetime as dt
import uuid

from sqlalchemy import select

from api.models.evaluation import EvaluationDataset, EvaluationFailure, EvaluationJob, EvaluationJobStatus, EvaluationQuestion, EvaluationResult
from api.models.organization import OrganizationMember, OrganizationRole
from api.models.user import User
from api.services.alerting import check_alert_rules


def _auth_header(token: str) -> dict:
    return {"Authorization": f"Bearer {token}"}


async def _owner_with_org(client, email: str, org_name: str = "Alerts Org"):
    token = (await client.post("/auth/register", json={"email": email, "password": "correct-horse-battery-staple", "accept_terms": True})).json()["access_token"]
    org_id = (await client.post("/organizations", json={"name": org_name}, headers=_auth_header(token))).json()["id"]
    return token, org_id


def _rule(**overrides) -> dict:
    return {"name": "Recall guard", "metric": "recall_at_5", "operator": "lt", "threshold": 0.8, **overrides}


async def test_an_organization_can_create_list_update_test_and_delete_its_own_quality_rule(client, db_session, register_payload):
    token, org_id = await _owner_with_org(client, register_payload["email"])
    base = f"/organizations/{org_id}/quality-alerts"

    created = await client.post(f"{base}/rules", json=_rule(), headers=_auth_header(token))
    assert created.status_code == 201 and created.json()["metric"] == "recall_at_5"
    rule_id = created.json()["id"]

    assert [r["id"] for r in (await client.get(f"{base}/rules", headers=_auth_header(token))).json()] == [rule_id]
    patched = await client.patch(f"{base}/rules/{rule_id}", json={"threshold": 0.9, "enabled": False}, headers=_auth_header(token))
    assert patched.status_code == 200 and patched.json()["threshold"] == 0.9 and patched.json()["enabled"] is False
    tested = await client.post(f"{base}/rules/{rule_id}/test", headers=_auth_header(token))
    assert tested.status_code == 200 and tested.json()["metric"] == "recall_at_5" and tested.json()["current_value"] is None  # no evaluation yet: honest None
    assert (await client.delete(f"{base}/rules/{rule_id}", headers=_auth_header(token))).status_code == 204
    assert (await client.get(f"{base}/rules", headers=_auth_header(token))).json() == []


async def test_only_rag_quality_metrics_and_sane_thresholds_are_accepted(client, db_session, register_payload):
    token, org_id = await _owner_with_org(client, register_payload["email"])
    base = f"/organizations/{org_id}/quality-alerts/rules"

    infra = await client.post(base, json=_rule(metric="cpu_percent"), headers=_auth_header(token))
    unknown = await client.post(base, json=_rule(metric="made_up"), headers=_auth_header(token))
    too_high = await client.post(base, json=_rule(threshold=7), headers=_auth_header(token))
    metrics = await client.get(f"/organizations/{org_id}/quality-alerts/metrics", headers=_auth_header(token))

    assert infra.status_code == 422 and unknown.status_code == 422 and too_high.status_code == 422
    assert "recall_at_5" in metrics.json()["metrics"] and "cpu_percent" not in metrics.json()["metrics"]


async def test_one_organization_never_sees_or_touches_anothers_rules(client, db_session, register_payload):
    token_a, org_a = await _owner_with_org(client, register_payload["email"], "Org A")
    token_b, org_b = await _owner_with_org(client, f"b-{uuid.uuid4().hex[:8]}@example.com", "Org B")
    rule_a = (await client.post(f"/organizations/{org_a}/quality-alerts/rules", json=_rule(), headers=_auth_header(token_a))).json()["id"]

    assert (await client.get(f"/organizations/{org_b}/quality-alerts/rules", headers=_auth_header(token_b))).json() == []
    base_b = f"/organizations/{org_b}/quality-alerts/rules/{rule_a}"
    assert (await client.patch(base_b, json={"threshold": 0.1}, headers=_auth_header(token_b))).status_code == 404
    assert (await client.post(f"{base_b}/test", headers=_auth_header(token_b))).status_code == 404
    assert (await client.delete(base_b, headers=_auth_header(token_b))).status_code == 404
    # B cannot reach A's data by putting A's org id in the path either (membership check)
    assert (await client.get(f"/organizations/{org_a}/quality-alerts/rules", headers=_auth_header(token_b))).status_code in (403, 404)
    assert [r["id"] for r in (await client.get(f"/organizations/{org_a}/quality-alerts/rules", headers=_auth_header(token_a))).json()] == [rule_a]


async def test_channels_are_validated_scoped_and_only_usable_by_their_own_organization(client, db_session, register_payload):
    token_a, org_a = await _owner_with_org(client, register_payload["email"], "Org A")
    token_b, org_b = await _owner_with_org(client, f"b-{uuid.uuid4().hex[:8]}@example.com", "Org B")
    channels_a = f"/organizations/{org_a}/quality-alerts/channels"

    http_url = await client.post(channels_a, json={"name": "w", "type": "webhook", "config": {"webhook_url": "http://example.com/hook"}}, headers=_auth_header(token_a))
    creds = await client.post(channels_a, json={"name": "w", "type": "webhook", "config": {"webhook_url": "https://user:pw@example.com/hook"}}, headers=_auth_header(token_a))
    bad_email = await client.post(channels_a, json={"name": "e", "type": "email", "config": {"email": "not-an-email"}}, headers=_auth_header(token_a))
    ok = await client.post(channels_a, json={"name": "ops", "type": "email", "config": {"email": "ops@example.com"}}, headers=_auth_header(token_a))
    assert http_url.status_code == 422 and creds.status_code == 422 and bad_email.status_code == 422 and ok.status_code == 201
    channel_a = ok.json()["id"]

    own = await client.post(f"/organizations/{org_a}/quality-alerts/rules", json=_rule(channel_id=channel_a), headers=_auth_header(token_a))
    foreign = await client.post(f"/organizations/{org_b}/quality-alerts/rules", json=_rule(channel_id=channel_a), headers=_auth_header(token_b))
    assert own.status_code == 201
    assert foreign.status_code == 404  # B can never send its quality data to A's inbox
    assert (await client.delete(f"/organizations/{org_b}/quality-alerts/channels/{channel_a}", headers=_auth_header(token_b))).status_code == 404
    assert (await client.delete(f"{channels_a}/{channel_a}", headers=_auth_header(token_a))).status_code == 204


async def test_a_customer_configured_rule_really_fires_and_its_alert_carries_the_autopsy(client, db_session, register_payload):
    """The whole point: configure through the API -> the scheduled check
    fires -> the customer reads the explained alert back through the API."""
    token, org_id = await _owner_with_org(client, register_payload["email"])
    dataset = EvaluationDataset(organization_id=uuid.UUID(org_id), name="ds")
    db_session.add(dataset)
    await db_session.flush()
    job = EvaluationJob(dataset_id=dataset.id, status=EvaluationJobStatus.completed, completed_at=dt.datetime.now(dt.timezone.utc))
    db_session.add(job)
    await db_session.flush()
    for value in (0.3, 0.5):
        question = EvaluationQuestion(dataset_id=dataset.id, question=f"Q{value}", expected_answer="A")
        db_session.add(question)
        await db_session.flush()
        db_session.add(EvaluationResult(
            question_id=question.id, evaluation_job_id=job.id, model_config_json={}, retrieved_documents=[], retrieved_chunks=[],
            actual_answer="x", metrics={"recall_at_5": value}, latency_ms=10,
        ))
        db_session.add(EvaluationFailure(evaluation_job_id=job.id, question_id=question.id, category="retrieval", error="miss"))
    await db_session.commit()

    await client.post(f"/organizations/{org_id}/quality-alerts/rules", json=_rule(), headers=_auth_header(token))
    triggered = await check_alert_rules(db_session)
    await db_session.commit()
    assert any("Recall guard" in h.message for h in triggered)

    history = await client.get(f"/organizations/{org_id}/quality-alerts/history", headers=_auth_header(token))

    assert history.status_code == 200
    message = history.json()[0]["message"]
    assert "recall_at_5=0." in message and "retrieval=2" in message and "evolution/retrieval/run" in message


async def test_the_quality_alert_routes_need_the_evaluation_manage_permission(client, db_session, register_payload):
    _owner_token, org_id = await _owner_with_org(client, register_payload["email"])
    email = f"viewer-{uuid.uuid4().hex[:8]}@example.com"
    viewer_token = (await client.post("/auth/register", json={"email": email, "password": "correct-horse-battery-staple", "accept_terms": True})).json()["access_token"]
    viewer = await db_session.scalar(select(User).where(User.email == email))
    db_session.add(OrganizationMember(organization_id=uuid.UUID(org_id), user_id=viewer.id, role=OrganizationRole.viewer))
    await db_session.commit()

    response = await client.post(f"/organizations/{org_id}/quality-alerts/rules", json=_rule(), headers=_auth_header(viewer_token))

    assert response.status_code == 403
