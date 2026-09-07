"""Partie 6.1.1 -- real, multi-tenant generate_response. Real litellm
mock at the same boundary as tests/test_agent_orchestrator.py;
search_with_context mocked at its own clean, already-tested boundary
(real end-to-end retrieval is covered by tests/test_retrieval_pipeline.py)."""

import uuid
from unittest.mock import AsyncMock

import litellm
import pytest
from litellm.types.utils import Choices, Message, ModelResponse

from api.config import settings
from api.models.organization import Organization
from api.services.citations import get_citations_by_response
from api.services.generation import generate_response


def _real_response(text: str) -> ModelResponse:
    message = Message(content=text, role="assistant")
    choice = Choices(message=message, index=0, finish_reason="stop")
    return ModelResponse(choices=[choice])


@pytest.fixture(autouse=True)
def _configure_key(monkeypatch):
    monkeypatch.setattr(settings, "ANTHROPIC_API_KEY", "sk-ant-test")


async def _make_org(db_session, name):
    org = Organization(name=name, slug=f"{name.lower().replace(' ', '-')}-{uuid.uuid4().hex[:8]}")
    db_session.add(org)
    await db_session.flush()
    return org


def _fake_chunks():
    return [
        {"chunk_id": str(uuid.uuid4()), "document_id": str(uuid.uuid4()), "content": "The sky scatters blue light.",
         "score": 0.9, "document_name": "physics.pdf", "file_type": "application/pdf"},
    ]


async def test_generate_response_persists_a_real_response(monkeypatch, db_session):
    """Validation criterion: la génération avec citations fonctionne."""
    monkeypatch.setattr("api.services.generation.search_with_context", AsyncMock(return_value=_fake_chunks()))
    monkeypatch.setattr(litellm, "acompletion", AsyncMock(return_value=_real_response("The sky is blue [1].")))

    org = await _make_org(db_session, "Generation Org")
    await db_session.commit()

    response = await generate_response(db_session, org.id, "Why is the sky blue?")
    await db_session.commit()

    assert response.query == "Why is the sky blue?"
    assert response.answer == "The sky is blue [1]."
    assert response.organization_id == org.id


async def test_generate_response_attaches_real_citations_by_default(monkeypatch, db_session):
    """Validation criterion: 5 citations par défaut."""
    chunks = [{"chunk_id": str(uuid.uuid4()), "document_id": str(uuid.uuid4()), "content": f"chunk {i}", "score": 0.9 - i * 0.05,
               "document_name": "d.pdf", "file_type": "pdf"} for i in range(8)]
    monkeypatch.setattr("api.services.generation.search_with_context", AsyncMock(return_value=chunks))
    monkeypatch.setattr(litellm, "acompletion", AsyncMock(return_value=_real_response("An answer.")))

    org = await _make_org(db_session, "Generation Org 2")
    await db_session.commit()
    response = await generate_response(db_session, org.id, "A question")
    await db_session.commit()

    citations = await get_citations_by_response(db_session, response.id)
    assert len(citations) == settings.CITATION_DEFAULT_COUNT


async def test_generate_response_includes_real_context_in_the_real_prompt(monkeypatch, db_session):
    """Validation criterion: cohérence -- RAG_search retourne les
    sources et elles nourrissent réellement le prompt."""
    mock_acompletion = AsyncMock(return_value=_real_response("ok"))
    monkeypatch.setattr("api.services.generation.search_with_context", AsyncMock(return_value=_fake_chunks()))
    monkeypatch.setattr(litellm, "acompletion", mock_acompletion)

    org = await _make_org(db_session, "Generation Org 3")
    await db_session.commit()
    await generate_response(db_session, org.id, "Why is the sky blue?")

    system_message = mock_acompletion.call_args.kwargs["messages"][0]["content"]
    assert "scatters blue light" in system_message
    assert "[1]" in system_message


async def test_generate_response_works_with_no_real_chunks_found(monkeypatch, db_session):
    """Validation criterion: robustesse -- pas de crash sans contexte réel."""
    monkeypatch.setattr("api.services.generation.search_with_context", AsyncMock(return_value=[]))
    monkeypatch.setattr(litellm, "acompletion", AsyncMock(return_value=_real_response("I don't have information on that.")))

    org = await _make_org(db_session, "Generation Org 4")
    await db_session.commit()
    response = await generate_response(db_session, org.id, "An unanswerable question")
    await db_session.commit()

    citations = await get_citations_by_response(db_session, response.id)
    assert citations == []


async def test_generate_response_respects_a_real_custom_citation_count(monkeypatch, db_session):
    chunks = [{"chunk_id": str(uuid.uuid4()), "document_id": str(uuid.uuid4()), "content": f"c{i}", "score": 0.9, "document_name": "d.pdf", "file_type": "pdf"} for i in range(3)]
    monkeypatch.setattr("api.services.generation.search_with_context", AsyncMock(return_value=chunks))
    monkeypatch.setattr(litellm, "acompletion", AsyncMock(return_value=_real_response("ok")))

    org = await _make_org(db_session, "Generation Org 5")
    await db_session.commit()
    response = await generate_response(db_session, org.id, "q", citation_count=1)
    await db_session.commit()

    citations = await get_citations_by_response(db_session, response.id)
    assert len(citations) == 1
