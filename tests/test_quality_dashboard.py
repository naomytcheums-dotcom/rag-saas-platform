"""Partie 6.2.12 -- quality dashboard. Fast SQLite suite."""

import datetime as dt
import uuid

from sqlalchemy import select

from api.config import settings
from api.models.agent_run import AgentRunRecord, AgentRunStatus
from api.models.citation import Citation
from api.models.document import Document, DocumentStatus
from api.models.organization import Organization
from api.models.response import Response
from api.models.user import User
from api.services.quality_dashboard import (
    export_quality_metrics, get_quality_dashboard, get_quality_metrics, get_quality_responses, get_quality_trends,
)


async def _make_org(db_session, name):
    org = Organization(name=name, slug=f"{name.lower().replace(' ', '-')}-{uuid.uuid4().hex[:8]}")
    db_session.add(org)
    await db_session.flush()
    return org


async def _make_document(db_session, org_id, name="doc.pdf"):
    document = Document(
        organization_id=org_id, name=name, file_key=f"documents/{uuid.uuid4()}/{name}",
        file_size=10, file_type="application/pdf", status=DocumentStatus.completed.value,
    )
    db_session.add(document)
    await db_session.flush()
    return document


async def _make_response(db_session, org_id, *, confidence=0.8, groundedness=0.7, faithfulness=0.9, hallucination=0.1,
                          has_contradictions=False, has_unsupported_claims=False, created_at=None):
    response = Response(
        organization_id=org_id, query="q", answer="a", confidence_score=confidence, groundedness_score=groundedness,
        faithfulness_score=faithfulness, hallucination_score=hallucination, has_contradictions=has_contradictions,
        has_unsupported_claims=has_unsupported_claims,
    )
    if created_at is not None:
        response.created_at = created_at
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


# --------------------------------------- get_quality_metrics --


async def test_get_quality_metrics_aggregates_real_averages_and_rates(db_session):
    """Validation criterion: les métriques sont calculées."""
    org = await _make_org(db_session, "Quality Metrics Org")
    r1 = await _make_response(db_session, org.id, confidence=0.9, has_contradictions=True)
    r2 = await _make_response(db_session, org.id, confidence=0.7, has_unsupported_claims=True)
    document = await _make_document(db_session, org.id)
    db_session.add(Citation(response_id=r1.id, document_id=document.id, text="t", relevance_score=0.9, citation_number=1))
    await db_session.commit()

    metrics = await get_quality_metrics(db_session, org.id)
    assert metrics["total_responses"] == 2
    assert metrics["avg_confidence_score"] == 0.8
    assert metrics["citation_rate"] == 0.5
    assert metrics["contradiction_rate"] == 0.5
    assert metrics["supported_claims_rate"] == 0.5


async def test_get_quality_metrics_is_isolated_by_real_organization(db_session):
    """Validation criterion: les données sont isolées par organisation."""
    org_a = await _make_org(db_session, "Isolation Org A")
    org_b = await _make_org(db_session, "Isolation Org B")
    await _make_response(db_session, org_a.id, confidence=0.9)
    await _make_response(db_session, org_b.id, confidence=0.1)
    await db_session.commit()

    metrics_a = await get_quality_metrics(db_session, org_a.id)
    assert metrics_a["total_responses"] == 1
    assert metrics_a["avg_confidence_score"] == 0.9


async def test_get_quality_metrics_is_honest_with_no_real_responses(db_session):
    """Validation criterion: robustesse -- aucune réponse."""
    org = await _make_org(db_session, "Quality Metrics Org Empty")
    await db_session.commit()

    metrics = await get_quality_metrics(db_session, org.id)
    assert metrics["total_responses"] == 0
    assert metrics["avg_confidence_score"] is None
    assert metrics["citation_rate"] == 0.0


# --------------------------------------- get_quality_trends --


async def test_get_quality_trends_groups_by_real_day(db_session):
    """Validation criterion: les tendances sont correctes."""
    org = await _make_org(db_session, "Quality Trends Org")
    now = dt.datetime.now(dt.timezone.utc)
    await _make_response(db_session, org.id, confidence=0.9, created_at=now)
    await _make_response(db_session, org.id, confidence=0.5, created_at=now - dt.timedelta(days=1))
    await db_session.commit()

    points = await get_quality_trends(db_session, org.id, period=30, metric="confidence_score")
    assert len(points) == 2
    assert {p["value"] for p in points} == {0.9, 0.5}


async def test_get_quality_trends_rejects_a_real_unknown_metric(db_session):
    org = await _make_org(db_session, "Quality Trends Org 2")
    await db_session.commit()
    try:
        await get_quality_trends(db_session, org.id, metric="not_a_real_column")
        assert False, "expected a real ValueError"
    except ValueError:
        pass


# --------------------------------------- get_quality_dashboard --


async def test_get_quality_dashboard_includes_real_top_documents_and_agents(db_session):
    """Validation criterion: le dashboard s'affiche correctement (top documents/agents)."""
    org = await _make_org(db_session, "Quality Dashboard Org")
    document = await _make_document(db_session, org.id, name="popular.pdf")
    response = await _make_response(db_session, org.id, faithfulness=0.95)
    db_session.add(Citation(response_id=response.id, document_id=document.id, text="t", relevance_score=0.9, citation_number=1))
    run = AgentRunRecord(agent_id="agent-xyz", input="q", status=AgentRunStatus.completed.value, response_id=response.id)
    db_session.add(run)
    await db_session.commit()

    dashboard = await get_quality_dashboard(db_session, org.id)
    assert dashboard["enabled"] is True
    assert dashboard["top_cited_documents"][0]["document_name"] == "popular.pdf"
    assert dashboard["top_faithful_agents"][0]["agent_id"] == "agent-xyz"
    assert dashboard["status_distribution"]["low"] == 1


async def test_get_quality_dashboard_is_a_real_no_op_when_disabled(db_session, monkeypatch):
    monkeypatch.setattr(settings, "QUALITY_DASHBOARD_ENABLED", False)
    org = await _make_org(db_session, "Quality Dashboard Org 2")
    await db_session.commit()
    assert await get_quality_dashboard(db_session, org.id) == {"enabled": False}


# --------------------------------------- get_quality_responses --


async def test_get_quality_responses_paginates_real_responses(db_session):
    """Validation criterion: les périodes/filtres/pagination fonctionnent."""
    org = await _make_org(db_session, "Quality Responses Org")
    for _ in range(3):
        await _make_response(db_session, org.id)
    await db_session.commit()

    page = await get_quality_responses(db_session, org.id, limit=2, offset=0)
    assert page["total"] == 3
    assert len(page["items"]) == 2


async def test_get_quality_responses_caps_the_real_page_size(db_session, monkeypatch):
    monkeypatch.setattr(settings, "QUALITY_DASHBOARD_MAX_RESPONSES", 2)
    org = await _make_org(db_session, "Quality Responses Org 2")
    for _ in range(3):
        await _make_response(db_session, org.id)
    await db_session.commit()

    page = await get_quality_responses(db_session, org.id, limit=50, offset=0)
    assert len(page["items"]) == 2


# --------------------------------------- export_quality_metrics --


async def test_export_quality_metrics_combines_real_metrics_and_trends(db_session):
    org = await _make_org(db_session, "Quality Export Org")
    await _make_response(db_session, org.id, confidence=0.8)
    await db_session.commit()

    export = await export_quality_metrics(db_session, org.id)
    assert export["metrics"]["total_responses"] == 1
    assert "confidence_score" in export["trends"]


# --------------------------------------- endpoints --


async def test_quality_dashboard_endpoint_requires_real_admin_access(client, db_session, register_payload):
    """Validation criterion: les permissions sont respectées."""
    owner_token, owner = await _register(client, db_session, register_payload["email"], register_payload["password"])
    org_response = await client.post("/organizations", json={"name": "Quality Endpoint Org"}, headers=_auth_header(owner_token))
    org_id = org_response.json()["id"]

    api_response = await client.get(f"/organizations/{org_id}/quality/dashboard", headers=_auth_header(owner_token))
    assert api_response.status_code == 200
    assert api_response.json()["enabled"] is True


async def test_quality_dashboard_endpoint_rejects_a_real_non_admin_member(client, db_session, register_payload):
    owner_token, owner = await _register(client, db_session, register_payload["email"], register_payload["password"])
    org_response = await client.post("/organizations", json={"name": "Quality Isolation Org"}, headers=_auth_header(owner_token))
    org_id = org_response.json()["id"]

    other_token, other = await _register(client, db_session, "other-quality@example.com")
    api_response = await client.get(f"/organizations/{org_id}/quality/dashboard", headers=_auth_header(other_token))
    assert api_response.status_code == 404


async def test_quality_export_endpoint_returns_real_csv(client, db_session, register_payload):
    """Validation criterion: les exports fonctionnent."""
    owner_token, owner = await _register(client, db_session, register_payload["email"], register_payload["password"])
    org_response = await client.post("/organizations", json={"name": "Quality Export Endpoint Org"}, headers=_auth_header(owner_token))
    org_id = org_response.json()["id"]

    api_response = await client.get(f"/organizations/{org_id}/quality/export?format=csv", headers=_auth_header(owner_token))
    assert api_response.status_code == 200
    assert "text/csv" in api_response.headers["content-type"]


async def test_quality_responses_endpoint_returns_real_paginated_list(client, db_session, register_payload):
    owner_token, owner = await _register(client, db_session, register_payload["email"], register_payload["password"])
    org_response = await client.post("/organizations", json={"name": "Quality Responses Endpoint Org"}, headers=_auth_header(owner_token))
    org_id = uuid.UUID(org_response.json()["id"])
    await _make_response(db_session, org_id)
    await db_session.commit()

    api_response = await client.get(f"/organizations/{org_id}/quality/responses", headers=_auth_header(owner_token))
    assert api_response.status_code == 200
    assert api_response.json()["total"] == 1
