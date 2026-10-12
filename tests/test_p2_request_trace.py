"""Spec 13.5.12 - GET /responses/{id}/trace joins the response, flight recording, agent run, agent steps and citations."""

import datetime as dt
import uuid

from sqlalchemy import select

from api.models.agent_run import AgentRunRecord
from api.models.agent_trace import AgentTrace
from api.models.citation import Citation
from api.models.flight_recording import FlightRecording
from api.models.response import Response
from api.models.user import User


def _auth(token):
    return {"Authorization": f"Bearer {token}"}


async def _register(client, email):
    payload = {"email": email, "password": "correct-horse-battery-staple", "accept_terms": True}
    return (await client.post("/auth/register", json=payload)).json()["access_token"]


async def _org(client, token, name):
    return uuid.UUID((await client.post("/organizations", json={"name": name}, headers=_auth(token))).json()["id"])


async def test_the_trace_joins_every_stage_of_one_answer(client, db_session, register_payload):
    token = await _register(client, register_payload["email"])
    org_id = await _org(client, token, "Trace Org")
    recording = FlightRecording(organization_id=org_id, query="refund?", stages_json=[{"stage": "retrieve", "ms": 12}, {"stage": "generate", "ms": 340}], total_duration_ms=352)
    db_session.add(recording)
    await db_session.flush()
    response = Response(organization_id=org_id, query="refund?", answer="30 days.", llm_provider="anthropic", llm_model="claude", retrieval_strategy="hybrid",
                        groundedness_score=0.8, flight_recording_id=recording.id)
    db_session.add(response)
    await db_session.flush()
    now = dt.datetime.now(dt.timezone.utc)
    run = AgentRunRecord(agent_id="support", organization_id=org_id, status="completed", input="refund?", response_id=response.id, started_at=now, completed_at=now + dt.timedelta(seconds=2))
    db_session.add(run)
    await db_session.flush()
    db_session.add_all([
        AgentTrace(agent_run_id=run.id, step_number=1, step_type="tool", description="search", status="completed", duration_ms=10, created_at=now),
        AgentTrace(agent_run_id=run.id, step_number=2, step_type="tool", description="calendar", status="failed", error="timeout", created_at=now),
    ])
    db_session.add(Citation(response_id=response.id, text="Refunds within 30 days", relevance_score=0.9, citation_number=1, document_name="policy.pdf"))
    await db_session.commit()

    body = (await client.get(f"/responses/{response.id}/trace", headers=_auth(token))).json()
    assert body["question"] == "refund?" and body["retrieval"] == {"strategy": "hybrid", "embedding_model": None, "citations_used": 1}
    assert body["generation"]["model"] == "claude" and body["checks"]["groundedness"] == 0.8
    assert body["agent_run"]["status"] == "completed" and body["agent_run"]["duration_seconds"] == 2.0
    assert body["recorded_stages"] == 2 and body["total_duration_ms"] == 352
    assert body["failed_agent_steps"] == [2]
    assert [(s["source"], s["order"]) for s in body["timeline"]] == [("flight_recorder", 0), ("flight_recorder", 1), ("agent", 1), ("agent", 2)]
    assert body["citations"][0]["document_name"] == "policy.pdf"


async def test_a_bare_response_still_has_a_trace(client, db_session, register_payload):
    token = await _register(client, register_payload["email"])
    org_id = await _org(client, token, "Bare Org")
    response = Response(organization_id=org_id, query="q", answer="a")
    db_session.add(response)
    await db_session.commit()
    body = (await client.get(f"/responses/{response.id}/trace", headers=_auth(token))).json()
    assert body["agent_run"] is None and body["timeline"] == [] and body["citations"] == []


async def test_another_organization_cannot_read_the_trace(client, db_session, register_payload):
    owner = await _register(client, register_payload["email"])
    org_id = await _org(client, owner, "Owner Org")
    response = Response(organization_id=org_id, query="secret question", answer="secret")
    db_session.add(response)
    await db_session.commit()
    stranger = await _register(client, "stranger@example.com")
    await _org(client, stranger, "Stranger Org")
    denied = await client.get(f"/responses/{response.id}/trace", headers=_auth(stranger))
    assert denied.status_code in (403, 404) and "secret" not in denied.text
    assert (await client.get(f"/responses/{response.id}/trace")).status_code in (401, 403)
