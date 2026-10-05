"""GET /responses/{response_id} -- the real, shared read endpoint exposing
every Partie 6.2.4/6.2.6/6.2.7/6.2.8/6.2.9/6.2.10 metric, reusing the
already-established require_response_member permission boundary."""

import uuid

from sqlalchemy import select

from api.models.response import Response
from api.models.user import User


async def _make_response(db_session, org_id, answer="An answer."):
    response = Response(organization_id=org_id, query="q", answer=answer)
    db_session.add(response)
    await db_session.flush()
    return response


def _auth_header(access_token: str) -> dict:
    return {"Authorization": f"Bearer {access_token}"}


async def _register(client, db_session, email: str, password: str = "correct-horse-battery-staple"):
    payload = {"email": email, "password": password, "accept_terms": True}
    access_token = (await client.post("/auth/register", json=payload)).json()["access_token"]
    user = await db_session.scalar(select(User).where(User.email == email))
    return access_token, user


async def test_get_response_endpoint_exposes_all_real_batch_6_2_fields(client, db_session, register_payload):
    """Validation criterion: les métriques persistées sont accessibles via l'API."""
    owner_token, owner = await _register(client, db_session, register_payload["email"], register_payload["password"])
    org_response = await client.post("/organizations", json={"name": "Response Detail Org"}, headers=_auth_header(owner_token))
    org_id = uuid.UUID(org_response.json()["id"])
    response = await _make_response(db_session, org_id)
    response.confidence_estimation = 0.5
    response.confidence_estimation_factors = {"citation_coverage": 0.5}
    response.claim_verification_status = "unverified"
    response.has_contradictions = True
    response.contradictions = [{"type": "factual"}]
    response.source_consistency_score = 0.9
    response.hallucination_score = 0.2
    response.groundedness_score = 0.6
    response.has_unsupported_claims = True
    response.unsupported_claims = [{"claim": "x", "reason": "no supporting citation found", "unsupported": True}]
    response.faithfulness_score = 0.7
    await db_session.commit()

    api_response = await client.get(f"/responses/{response.id}", headers=_auth_header(owner_token))
    assert api_response.status_code == 200
    body = api_response.json()
    assert body["confidence_estimation"] == 0.5
    assert body["claim_verification_status"] == "unverified"
    assert body["has_contradictions"] is True
    assert body["contradictions"] == [{"type": "factual"}]
    assert body["source_consistency_score"] == 0.9
    assert body["has_unsupported_claims"] is True
    assert body["faithfulness_score"] == 0.7
    assert body["hallucination_score"] == 0.2
    assert body["groundedness_score"] == 0.6


async def test_get_response_endpoint_defaults_are_honestly_null_before_any_real_generation(client, db_session, register_payload):
    """Validation criterion: robustesse -- une réponse sans métriques calculées."""
    owner_token, owner = await _register(client, db_session, register_payload["email"], register_payload["password"])
    org_response = await client.post("/organizations", json={"name": "Response Detail Org 2"}, headers=_auth_header(owner_token))
    org_id = uuid.UUID(org_response.json()["id"])
    response = await _make_response(db_session, org_id)
    await db_session.commit()

    api_response = await client.get(f"/responses/{response.id}", headers=_auth_header(owner_token))
    assert api_response.status_code == 200
    body = api_response.json()
    assert body["confidence_estimation"] is None
    assert body["has_contradictions"] is False
    assert body["contradictions"] is None


async def test_get_response_endpoint_exposes_real_provenance_fields(client, db_session, register_payload):
    """Hardening Mission, Phase 7 -- REGRESSION: a Response's own real
    retrieval/LLM provenance is now reachable through this same
    endpoint."""
    owner_token, owner = await _register(client, db_session, register_payload["email"], register_payload["password"])
    org_response = await client.post("/organizations", json={"name": "Provenance Detail Org"}, headers=_auth_header(owner_token))
    org_id = uuid.UUID(org_response.json()["id"])
    response = await _make_response(db_session, org_id)
    response.retrieval_strategy = "hybrid"
    response.embedding_model = "sentence-transformers/all-MiniLM-L6-v2"
    response.llm_provider = "anthropic"
    response.llm_model = "claude-3-5-sonnet-20241022"
    await db_session.commit()

    api_response = await client.get(f"/responses/{response.id}", headers=_auth_header(owner_token))
    assert api_response.status_code == 200
    body = api_response.json()
    assert body["retrieval_strategy"] == "hybrid"
    assert body["embedding_model"] == "sentence-transformers/all-MiniLM-L6-v2"
    assert body["llm_provider"] == "anthropic"
    assert body["llm_model"] == "claude-3-5-sonnet-20241022"
    assert body["flight_recording_id"] is None


async def test_get_response_flight_recording_endpoint_returns_404_when_none_exists(client, db_session, register_payload):
    owner_token, owner = await _register(client, db_session, register_payload["email"], register_payload["password"])
    org_response = await client.post("/organizations", json={"name": "No Flight Org"}, headers=_auth_header(owner_token))
    org_id = uuid.UUID(org_response.json()["id"])
    response = await _make_response(db_session, org_id)
    await db_session.commit()

    api_response = await client.get(f"/responses/{response.id}/flight-recording", headers=_auth_header(owner_token))
    assert api_response.status_code == 404


async def test_get_response_flight_recording_endpoint_returns_the_real_linked_trace(client, db_session, register_payload):
    from api.models.flight_recording import FlightRecording

    owner_token, owner = await _register(client, db_session, register_payload["email"], register_payload["password"])
    org_response = await client.post("/organizations", json={"name": "Flight Trace Org"}, headers=_auth_header(owner_token))
    org_id = uuid.UUID(org_response.json()["id"])
    recording = FlightRecording(organization_id=org_id, query="q", stages_json=[{"stage": "hyde", "data": {"ran": True}, "duration_ms": 12}], total_duration_ms=42)
    db_session.add(recording)
    await db_session.flush()
    response = await _make_response(db_session, org_id)
    response.flight_recording_id = recording.id
    await db_session.commit()

    api_response = await client.get(f"/responses/{response.id}/flight-recording", headers=_auth_header(owner_token))
    assert api_response.status_code == 200
    body = api_response.json()
    assert body["total_duration_ms"] == 42
    assert body["stages_json"] == [{"stage": "hyde", "data": {"ran": True}, "duration_ms": 12}]


async def test_non_member_cannot_read_a_response_detail(client, db_session, register_payload):
    """Validation criterion: les permissions sont respectées."""
    owner_token, owner = await _register(client, db_session, register_payload["email"], register_payload["password"])
    org_response = await client.post("/organizations", json={"name": "Response Detail Isolation Org"}, headers=_auth_header(owner_token))
    org_id = uuid.UUID(org_response.json()["id"])
    response = await _make_response(db_session, org_id)
    await db_session.commit()

    other_token, other = await _register(client, db_session, "other-response-detail@example.com")
    api_response = await client.get(f"/responses/{response.id}", headers=_auth_header(other_token))
    assert api_response.status_code == 404


async def test_get_response_endpoint_requires_real_authentication(client, db_session):
    response_id = uuid.uuid4()
    api_response = await client.get(f"/responses/{response_id}")
    assert api_response.status_code in (401, 403)
