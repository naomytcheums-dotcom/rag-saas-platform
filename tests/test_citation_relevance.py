"""Partie 6.1.6 -- score de pertinence. Fast SQLite suite."""

import uuid

from sqlalchemy import select

from api.models.citation import Citation
from api.models.response import Response
from api.models.user import User
from api.services.citation_relevance import (
    calculate_relevance_label, enrich_citation_with_relevance, enrich_citations_with_relevance,
    format_relevance_score, get_relevance_color,
)


async def _make_org(db_session, name):
    from api.models.organization import Organization

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


# --------------------------------------- calculate_relevance_label --


def test_calculate_relevance_label_high_at_and_above_the_real_threshold():
    """Validation criterion: le score est catégorisé (haut/moyen/bas)."""
    assert calculate_relevance_label(0.7) == "high"
    assert calculate_relevance_label(0.95) == "high"


def test_calculate_relevance_label_medium_between_the_real_thresholds():
    assert calculate_relevance_label(0.4) == "medium"
    assert calculate_relevance_label(0.69) == "medium"


def test_calculate_relevance_label_low_below_the_real_medium_threshold():
    assert calculate_relevance_label(0.0) == "low"
    assert calculate_relevance_label(0.39) == "low"


# --------------------------------------- format_relevance_score --


def test_format_relevance_score_renders_a_real_percentage_by_default():
    """Validation criterion: le score est affiché de manière lisible."""
    assert format_relevance_score(0.856) == "86%"


def test_format_relevance_score_honors_the_real_percentage_toggle(monkeypatch):
    from api.config import settings

    monkeypatch.setattr(settings, "RELEVANCE_SHOW_PERCENTAGE", False)
    assert format_relevance_score(0.856) == "0.86"


# --------------------------------------- get_relevance_color --


def test_get_relevance_color_matches_the_real_same_label():
    """Validation criterion: une couleur est associée au score."""
    assert get_relevance_color(0.9) == "green"
    assert get_relevance_color(0.5) == "orange"
    assert get_relevance_color(0.1) == "red"


# --------------------------------------- enrich_citation_with_relevance --


def test_enrich_citation_with_relevance_sets_the_real_label_from_the_real_score():
    """Validation criterion: cohérence -- le label vient du vrai score."""
    citation = Citation(response_id=uuid.uuid4(), text="t", relevance_score=0.9, citation_number=1)
    enriched = enrich_citation_with_relevance(citation)
    assert enriched.relevance_label == "high"


def test_enrich_citation_with_relevance_refreshes_a_stale_label_against_current_thresholds(monkeypatch):
    """Validation criterion: robustesse -- les seuils configurés peuvent
    changer, un label déjà persisté ne doit pas rester obsolète."""
    from api.config import settings

    citation = Citation(response_id=uuid.uuid4(), text="t", relevance_score=0.5, citation_number=1, relevance_label="low")
    monkeypatch.setattr(settings, "RELEVANCE_THRESHOLD_MEDIUM", 0.4)
    monkeypatch.setattr(settings, "RELEVANCE_THRESHOLD_HIGH", 0.9)

    enriched = enrich_citation_with_relevance(citation)
    assert enriched.relevance_label == "medium"


def test_enrich_citations_with_relevance_enriches_every_real_citation():
    citations = [
        Citation(response_id=uuid.uuid4(), text="a", relevance_score=0.9, citation_number=1),
        Citation(response_id=uuid.uuid4(), text="b", relevance_score=0.1, citation_number=2),
    ]
    enriched = enrich_citations_with_relevance(citations)
    assert enriched[0].relevance_label == "high"
    assert enriched[1].relevance_label == "low"


# --------------------------------------- add_citations_to_response now populates relevance_label --


async def test_add_citations_to_response_populates_real_relevance_label(db_session):
    """Validation criterion: le label est capturé à la création de la citation."""
    from api.services.citations import add_citations_to_response

    org = await _make_org(db_session, "Relevance Org")
    response = await _make_response(db_session, org.id)
    await db_session.commit()
    chunks = [{"chunk_id": str(uuid.uuid4()), "document_id": str(uuid.uuid4()), "content": "c", "score": 0.95,
               "document_name": "d.pdf", "file_type": "pdf"}]

    citations = await add_citations_to_response(db_session, response, chunks)
    await db_session.commit()

    assert citations[0].relevance_label == "high"


# --------------------------------------- endpoint --


async def test_citation_endpoint_returns_real_relevance_label(client, db_session, register_payload):
    """Validation criterion: le formatage fonctionne + permissions respectées."""
    owner_token, owner = await _register(client, db_session, register_payload["email"], register_payload["password"])
    org_response = await client.post("/organizations", json={"name": "Relevance Endpoint Org"}, headers=_auth_header(owner_token))
    org_id = uuid.UUID(org_response.json()["id"])
    response = await _make_response(db_session, org_id)
    await db_session.commit()
    citation = Citation(response_id=response.id, text="t", relevance_score=0.2, citation_number=1)
    db_session.add(citation)
    await db_session.commit()

    api_response = await client.get(f"/citations/{citation.id}", headers=_auth_header(owner_token))
    assert api_response.status_code == 200
    assert api_response.json()["relevance_label"] == "low"
