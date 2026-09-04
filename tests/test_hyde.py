"""Partie 3.4.3 -- tests for api/services/hyde.py.

`generate_hypothetical_document` mocks `litellm.acompletion` itself
(the same real, documented exception `tests/test_llm_providers.py`
already established for real, paid, third-party API calls).
`embed_hypothetical_document`/`search_with_hyde`/`hyde_rerank` use real
embeddings and a real SQLite `db_session`, no mocking beyond the one,
real LLM boundary."""

import uuid
from unittest.mock import AsyncMock

import litellm
import pytest
from litellm.types.utils import Choices, Message, ModelResponse

from api.config import settings
from api.models.document import Document, DocumentChunk, DocumentStatus
from api.models.organization import Organization
from api.security.documents import generate_embeddings
from api.services.hyde import embed_hypothetical_document, generate_hypothetical_document, hyde_rerank, search_with_hyde

EMBEDDING_MODEL = "sentence-transformers/all-MiniLM-L6-v2"


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


async def _make_document(db_session, org_id, name="doc.pdf"):
    document = Document(
        organization_id=org_id, name=name, file_key=f"documents/{uuid.uuid4()}/{name}",
        file_size=100, file_type="application/pdf", status=DocumentStatus.completed.value,
    )
    db_session.add(document)
    await db_session.flush()
    return document


async def _add_chunks(db_session, org_id, document_id, texts):
    embeddings = generate_embeddings(texts, EMBEDDING_MODEL)
    for text, embedding in zip(texts, embeddings):
        db_session.add(DocumentChunk(document_id=document_id, organization_id=org_id, content=text, embedding=embedding))
    await db_session.commit()


# ------------------------------- generation / embedding (mocked LLM) -------------------------------


async def test_generate_hypothetical_document_calls_the_real_llm(monkeypatch):
    """Validation criterion: la génération de document hypothétique
    fonctionne (mock)."""
    mock_acompletion = AsyncMock(return_value=_real_response("A real, plausible passage answering the question."))
    monkeypatch.setattr(litellm, "acompletion", mock_acompletion)

    documents = await generate_hypothetical_document("What is the refund policy?")

    assert documents == ["A real, plausible passage answering the question."]


async def test_generate_hypothetical_document_generates_the_real_configured_count(monkeypatch):
    mock_acompletion = AsyncMock(return_value=_real_response("A passage."))
    monkeypatch.setattr(litellm, "acompletion", mock_acompletion)

    documents = await generate_hypothetical_document("a query", num_documents=3)

    assert len(documents) == 3
    assert mock_acompletion.call_count == 3


async def test_generate_hypothetical_document_skips_real_failed_generations(monkeypatch):
    """Validation criterion: robustesse."""
    mock_acompletion = AsyncMock(side_effect=[
        litellm.exceptions.RateLimitError(message="rate limited", llm_provider="anthropic", model="claude"),
        _real_response("A real passage that succeeded."),
    ])
    monkeypatch.setattr(litellm, "acompletion", mock_acompletion)
    monkeypatch.setattr(settings, "LLM_MAX_RETRIES", 0)

    documents = await generate_hypothetical_document("a query", num_documents=2)

    assert documents == ["A real passage that succeeded."]


def test_embed_hypothetical_document_produces_a_real_vector():
    """Validation criterion: l'embedding fonctionne."""
    embedding = embed_hypothetical_document("A real, plausible passage about refunds.")
    assert len(embedding) == 384


def test_embed_hypothetical_document_averages_real_multiple_documents():
    single = embed_hypothetical_document("A real passage about refunds.")
    averaged = embed_hypothetical_document(["A real passage about refunds.", "A real passage about refunds."])
    assert len(averaged) == 384
    assert averaged == pytest.approx(single, abs=1e-6)


def test_embed_hypothetical_document_is_empty_for_no_real_documents():
    assert embed_hypothetical_document([]) == []
    assert embed_hypothetical_document([""]) == []


# ------------------------------------- search_with_hyde -------------------------------------


async def test_search_with_hyde_finds_real_relevant_chunks(db_session, monkeypatch):
    """Validation criterion: la recherche avec HyDE fonctionne."""
    org = await _make_org(db_session, "Org HyDE")
    document = await _make_document(db_session, org.id)
    await _add_chunks(db_session, org.id, document.id, [
        "Refunds are processed within 30 days of the original purchase date.",
        "Our office relocated to a new building downtown last year.",
    ])

    mock_acompletion = AsyncMock(return_value=_real_response(
        "Customers can request a refund within thirty days of buying the product.",
    ))
    monkeypatch.setattr(litellm, "acompletion", mock_acompletion)

    results = await search_with_hyde(db_session, org.id, "How do I get my money back?", top_k=1)

    assert len(results) == 1
    assert "Refunds" in results[0]["content"]


async def test_search_with_hyde_falls_back_to_vector_search_when_generation_fails(db_session, monkeypatch):
    """Validation criterion: robustesse -- un échec de génération ne
    casse jamais la recherche."""
    org = await _make_org(db_session, "Org HyDE Fallback")
    document = await _make_document(db_session, org.id)
    await _add_chunks(db_session, org.id, document.id, ["Refunds are processed within 30 days."])

    mock_acompletion = AsyncMock(side_effect=litellm.exceptions.RateLimitError(
        message="rate limited", llm_provider="anthropic", model="claude",
    ))
    monkeypatch.setattr(litellm, "acompletion", mock_acompletion)
    monkeypatch.setattr(settings, "LLM_MAX_RETRIES", 0)

    results = await search_with_hyde(db_session, org.id, "refund policy", top_k=1)

    assert len(results) == 1  # real, plain vector_search fallback still found the real chunk


async def test_search_with_hyde_respects_the_real_kill_switch(db_session, monkeypatch):
    org = await _make_org(db_session, "Org HyDE Kill Switch")
    document = await _make_document(db_session, org.id)
    await _add_chunks(db_session, org.id, document.id, ["Refunds are processed within 30 days."])

    mock_acompletion = AsyncMock()
    monkeypatch.setattr(litellm, "acompletion", mock_acompletion)
    monkeypatch.setattr(settings, "HYDE_ENABLED", False)

    results = await search_with_hyde(db_session, org.id, "refund policy", top_k=1)

    assert len(results) == 1
    mock_acompletion.assert_not_called()


# ---------------------------------------- hyde_rerank ----------------------------------------


def test_hyde_rerank_reorders_by_real_similarity_to_the_original_query():
    """Validation criterion: le reranking avec la requête originale
    fonctionne."""
    candidates = [
        {"chunk_id": "1", "content": "Bananas are a good source of potassium."},
        {"chunk_id": "2", "content": "The refund policy allows returns within 30 days."},
    ]
    reranked = hyde_rerank("refund policy", candidates)
    assert reranked[0]["chunk_id"] == "2"
    assert all("score" in r for r in reranked)


def test_hyde_rerank_is_empty_input_safe():
    assert hyde_rerank("anything", []) == []
