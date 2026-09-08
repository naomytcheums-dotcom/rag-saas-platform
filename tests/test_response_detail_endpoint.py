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
    await db_session.commit()

    api_response = await client.get(f"/responses/{response.id}", headers=_auth_header(owner_token))
    assert api_response.status_code == 200
    body = api_response.json()
    assert body["confidence_estimation"] == 0.5
    assert body["claim_verification_status"] == "unverified"
    assert body["has_contradictions"] is True
    assert body["contradictions"] == [{"type": "factual"}]
    assert body["source_consistency_score"] == 0.9
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
