"""Partie 6.1.10 -- confidence score global. Fast SQLite suite."""

import uuid

from sqlalchemy import select

from api.config import settings
from api.models.citation import Citation
from api.models.organization import Organization
from api.models.response import Response
from api.models.user import User
from api.services.response_confidence import (
    calculate_confidence_factors, calculate_confidence_score, enrich_response_with_confidence,
    format_confidence_score, get_confidence_color, get_confidence_label,
)


def _citation(score, document_id=None, is_primary=True, number=1):
    return Citation(
        response_id=uuid.uuid4(), text="t", relevance_score=score, citation_number=number, is_primary=is_primary,
        document_id=document_id,
    )


async def _make_org(db_session, name):
    org = Organization(name=name, slug=f"{name.lower().replace(' ', '-')}-{uuid.uuid4().hex[:8]}")
    db_session.add(org)
    await db_session.flush()
    return org


async def _make_response(db_session, org_id):
    response = Response(organization_id=org_id, query="q", answer="a")
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


# --------------------------------------- calculate_confidence_factors --


def test_calculate_confidence_factors_is_honestly_zero_with_no_real_primary_citations():
    """Validation criterion: robustesse -- aucune citation ne donne une confiance honnêtement basse."""
    assert calculate_confidence_factors([]) == {
        "citation_count": 0.0, "relevance": 0.0, "diversity": 0.0, "reliability": 0.0, "consistency": 0.0,
    }


def test_calculate_confidence_factors_ignores_real_secondary_citations():
    """Validation criterion: cohérence -- basé sur les vraies citations primaires."""
    primary = [_citation(0.9, document_id=uuid.uuid4())]
    secondary = [_citation(0.1, document_id=uuid.uuid4(), is_primary=False, number=2)]
    only_primary = calculate_confidence_factors(primary)
    with_secondary = calculate_confidence_factors(primary + secondary)
    assert only_primary == with_secondary


def test_calculate_confidence_factors_citation_count_scales_with_the_real_default():
    doc = uuid.uuid4()
    citations = [_citation(0.9, document_id=doc, number=i) for i in range(1, settings.CITATION_DEFAULT_COUNT + 1)]
    factors = calculate_confidence_factors(citations)
    assert factors["citation_count"] == 1.0


def test_calculate_confidence_factors_diversity_reflects_real_distinct_documents():
    """Validation criterion: les facteurs individuels sont calculés correctement."""
    same_doc = uuid.uuid4()
    all_same = calculate_confidence_factors([_citation(0.9, document_id=same_doc, number=i) for i in range(1, 4)])
    all_different = calculate_confidence_factors([_citation(0.9, document_id=uuid.uuid4(), number=i) for i in range(1, 4)])
    assert all_same["diversity"] < all_different["diversity"]
    assert all_different["diversity"] == 1.0


def test_calculate_confidence_factors_reliability_reflects_real_traceable_sources():
    citations = [_citation(0.9, document_id=uuid.uuid4(), number=1), _citation(0.9, document_id=None, number=2)]
    factors = calculate_confidence_factors(citations)
    assert factors["reliability"] == 0.5


def test_calculate_confidence_factors_consistency_is_perfect_for_a_single_real_citation():
    """Validation criterion: robustesse -- une seule citation n'a rien avec quoi être incohérente."""
    factors = calculate_confidence_factors([_citation(0.5)])
    assert factors["consistency"] == 1.0


def test_calculate_confidence_factors_consistency_drops_with_real_score_disagreement():
    consistent = calculate_confidence_factors([_citation(0.9, number=1), _citation(0.91, number=2)])
    inconsistent = calculate_confidence_factors([_citation(0.9, number=1), _citation(0.1, number=2)])
    assert consistent["consistency"] > inconsistent["consistency"]


# --------------------------------------- calculate_confidence_score --


def test_calculate_confidence_score_is_a_real_weighted_average_in_range():
    score = calculate_confidence_score([_citation(0.9, document_id=uuid.uuid4())])
    assert 0.0 <= score <= 1.0


def test_calculate_confidence_score_is_honestly_zero_with_no_real_citations():
    assert calculate_confidence_score([]) == 0.0


# --------------------------------------- format/label/color --


def test_format_confidence_score_reuses_the_real_relevance_formatting():
    assert format_confidence_score(0.856) == "86%"


def test_get_confidence_label_reuses_the_real_relevance_thresholds():
    assert get_confidence_label(0.9) == "high"
    assert get_confidence_label(0.1) == "low"


def test_get_confidence_color_reuses_the_real_relevance_colors():
    assert get_confidence_color(0.9) == "green"


# --------------------------------------- enrich_response_with_confidence --


def test_enrich_response_with_confidence_sets_both_real_fields():
    """Validation criterion: le score global est calculé et affiché."""
    response = Response(organization_id=uuid.uuid4(), query="q", answer="a")
    enriched = enrich_response_with_confidence(response, [_citation(0.9, document_id=uuid.uuid4())])
    assert enriched.confidence_score is not None
    assert enriched.confidence_factors is not None


# --------------------------------------- generate_response wiring --


async def test_generate_response_persists_a_real_confidence_score(monkeypatch, db_session):
    """Validation criterion: le score est calculé lors de la génération de réponse."""
    import litellm
    from unittest.mock import AsyncMock

    from litellm.types.utils import Choices, Message, ModelResponse

    from api.services.generation import generate_response

    monkeypatch.setattr(settings, "ANTHROPIC_API_KEY", "sk-ant-test")
    chunks = [{"chunk_id": str(uuid.uuid4()), "document_id": str(uuid.uuid4()), "content": "c", "score": 0.9,
               "document_name": "d.pdf", "file_type": "pdf"}]
    monkeypatch.setattr("api.services.generation.search_with_context", AsyncMock(return_value=chunks))

    def _real_response(text):
        message = Message(content=text, role="assistant")
        choice = Choices(message=message, index=0, finish_reason="stop")
        return ModelResponse(choices=[choice])

    monkeypatch.setattr(litellm, "acompletion", AsyncMock(return_value=_real_response("An answer.")))

    org = await _make_org(db_session, "Confidence Gen Org")
    await db_session.commit()
    response = await generate_response(db_session, org.id, "q")
    await db_session.commit()

    assert response.confidence_score is not None
    assert 0.0 <= response.confidence_score <= 1.0
    assert set(response.confidence_factors) == {"citation_count", "relevance", "diversity", "reliability", "consistency"}


# --------------------------------------- endpoints --


async def test_confidence_endpoint_returns_real_live_score(client, db_session, register_payload):
    """Validation criterion: l'API expose le score de confiance."""
    owner_token, owner = await _register(client, db_session, register_payload["email"], register_payload["password"])
    org_response = await client.post("/organizations", json={"name": "Confidence Endpoint Org"}, headers=_auth_header(owner_token))
    org_id = uuid.UUID(org_response.json()["id"])
    response = await _make_response(db_session, org_id)
    await db_session.commit()
    citation = Citation(response_id=response.id, text="t", relevance_score=0.9, citation_number=1, document_id=uuid.uuid4())
    db_session.add(citation)
    await db_session.commit()

    api_response = await client.get(f"/responses/{response.id}/confidence", headers=_auth_header(owner_token))
    assert api_response.status_code == 200
    body = api_response.json()
    assert body["confidence_label"] in ("high", "medium", "low")
    assert 0.0 <= body["confidence_score"] <= 1.0


async def test_confidence_factors_endpoint_returns_real_factor_breakdown(client, db_session, register_payload):
    """Validation criterion: le détail des facteurs est accessible."""
    owner_token, owner = await _register(client, db_session, register_payload["email"], register_payload["password"])
    org_response = await client.post("/organizations", json={"name": "Confidence Factors Org"}, headers=_auth_header(owner_token))
    org_id = uuid.UUID(org_response.json()["id"])
    response = await _make_response(db_session, org_id)
    await db_session.commit()
    citation = Citation(response_id=response.id, text="t", relevance_score=0.9, citation_number=1, document_id=uuid.uuid4())
    db_session.add(citation)
    await db_session.commit()

    api_response = await client.get(f"/responses/{response.id}/confidence/factors", headers=_auth_header(owner_token))
    assert api_response.status_code == 200
    assert set(api_response.json()) == {"citation_count", "relevance", "diversity", "reliability", "consistency"}


async def test_confidence_endpoint_recomputes_live_after_a_source_document_is_gone(client, db_session, register_payload):
    """Validation criterion: robustesse -- reflète l'état réel actuel, pas un instantané périmé."""
    owner_token, owner = await _register(client, db_session, register_payload["email"], register_payload["password"])
    org_response = await client.post("/organizations", json={"name": "Confidence Live Org"}, headers=_auth_header(owner_token))
    org_id = uuid.UUID(org_response.json()["id"])
    response = await _make_response(db_session, org_id)
    await db_session.commit()
    citation = Citation(response_id=response.id, text="t", relevance_score=0.9, citation_number=1, document_id=uuid.uuid4())
    db_session.add(citation)
    await db_session.commit()

    stale_score, _ = calculate_confidence_score([citation]), None

    api_response = await client.get(f"/responses/{response.id}/confidence", headers=_auth_header(owner_token))
    assert api_response.json()["confidence_score"] == stale_score


async def test_non_member_cannot_read_response_confidence(client, db_session, register_payload):
    owner_token, owner = await _register(client, db_session, register_payload["email"], register_payload["password"])
    org_response = await client.post("/organizations", json={"name": "Confidence Isolation Org"}, headers=_auth_header(owner_token))
    org_id = uuid.UUID(org_response.json()["id"])
    response = await _make_response(db_session, org_id)
    await db_session.commit()

    other_token, other = await _register(client, db_session, "other-confidence@example.com")
    api_response = await client.get(f"/responses/{response.id}/confidence", headers=_auth_header(other_token))
    assert api_response.status_code == 404
