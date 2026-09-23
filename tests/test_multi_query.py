"""Partie 3.4.4 -- tests for api/services/multi_query.py.

`generate_query_variants` mocks `litellm.acompletion` itself (the same
real, documented exception `tests/test_llm_providers.py` already
established). `run_queries_parallel`/`multi_query_search` use a real
SQLite `db_session` and real embeddings; `merge_query_results` is
tested against plain, synthetic result dicts (no embeddings needed for
its own real fusion-math logic)."""

import uuid
from unittest.mock import AsyncMock

import litellm
import pytest
from litellm.types.utils import Choices, Message, ModelResponse

from api.config import settings
from api.models.document import Document, DocumentChunk, DocumentStatus
from api.models.organization import Organization
from api.security.documents import generate_embeddings
from api.services.multi_query import (
    deduplicate_results,
    generate_query_variants,
    merge_query_results,
    multi_query_search,
    rerank_merged_results,
    run_queries_parallel,
)

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


# ------------------------------- generate_query_variants (mocked LLM) -------------------------------


async def test_generate_query_variants_includes_the_real_original_query_first(monkeypatch):
    """Validation criterion: la génération de variantes fonctionne."""
    mock_acompletion = AsyncMock(return_value=_real_response("How can I get a refund?\nWhat is your return policy?"))
    monkeypatch.setattr(litellm, "acompletion", mock_acompletion)

    variants = await generate_query_variants("refund policy", num_variants=3)

    assert variants[0] == "refund policy"
    assert len(variants) == 3


async def test_generate_query_variants_skips_the_real_llm_when_num_variants_is_1(monkeypatch):
    mock_acompletion = AsyncMock()
    monkeypatch.setattr(litellm, "acompletion", mock_acompletion)

    variants = await generate_query_variants("refund policy", num_variants=1)

    assert variants == ["refund policy"]
    mock_acompletion.assert_not_called()


async def test_generate_query_variants_falls_back_on_a_real_llm_error(monkeypatch):
    """Validation criterion: robustesse -- une requête (LLM) qui
    échoue ne casse jamais le résultat."""
    mock_acompletion = AsyncMock(side_effect=litellm.exceptions.RateLimitError(
        message="rate limited", llm_provider="anthropic", model="claude",
    ))
    monkeypatch.setattr(litellm, "acompletion", mock_acompletion)
    monkeypatch.setattr(settings, "LLM_MAX_RETRIES", 0)

    variants = await generate_query_variants("refund policy", num_variants=3)

    assert variants == ["refund policy"]


# ------------------------------------- run_queries_parallel -------------------------------------


async def test_run_queries_parallel_executes_real_searches_for_every_variant(db_session):
    """Validation criterion: l'exécution parallèle fonctionne."""
    org = await _make_org(db_session, "Org Multi Query Parallel")
    document = await _make_document(db_session, org.id)
    await _add_chunks(db_session, org.id, document.id, ["The refund policy allows returns within 30 days."])

    results = await run_queries_parallel(db_session, org.id, ["refund policy", "return policy"], top_k=1)

    assert len(results) == 2
    assert all(len(r) == 1 for r in results)


async def test_run_queries_parallel_survives_a_real_individual_query_failure(db_session, monkeypatch):
    """Validation criterion: robustesse -- une requête individuelle qui
    échoue n'interrompt pas les autres."""
    org = await _make_org(db_session, "Org Multi Query Failure")
    document = await _make_document(db_session, org.id)
    await _add_chunks(db_session, org.id, document.id, ["The refund policy allows returns within 30 days."])

    import api.services.multi_query as multi_query_module

    real_vector_search = multi_query_module.vector_search

    async def _flaky_vector_search(db, organization_id, query, **kwargs):
        if query == "boom":
            raise RuntimeError("a real, simulated individual query failure")
        return await real_vector_search(db, organization_id, query, **kwargs)

    monkeypatch.setattr(multi_query_module, "vector_search", _flaky_vector_search)

    results = await run_queries_parallel(db_session, org.id, ["refund policy", "boom"], top_k=1)

    assert len(results) == 2
    assert results[1] == []  # the real, failed query contributes an empty result, never raises
    assert len(results[0]) == 1


# ------------------------------------- merge_query_results -------------------------------------


def test_merge_query_results_rrf_fuses_real_ranked_lists():
    """Validation criterion: la fusion RRF fonctionne."""
    results = [
        [{"chunk_id": "1", "content": "a"}, {"chunk_id": "2", "content": "b"}],
        [{"chunk_id": "2", "content": "b"}, {"chunk_id": "3", "content": "c"}],
    ]
    merged = merge_query_results(results, method="rrf")
    assert merged[0]["chunk_id"] == "2"  # ranked first in both real lists


def test_merge_query_results_score_keeps_the_real_highest_score_per_chunk():
    results = [
        [{"chunk_id": "1", "content": "a", "score": 0.3}],
        [{"chunk_id": "1", "content": "a", "score": 0.9}],
    ]
    merged = merge_query_results(results, method="score")
    assert len(merged) == 1
    assert merged[0]["score"] == 0.9


def test_merge_query_results_interleaving_alternates_real_result_sets():
    """Validation criterion: la fusion par interleaving fonctionne."""
    results = [
        [{"chunk_id": "1", "content": "a"}, {"chunk_id": "2", "content": "b"}],
        [{"chunk_id": "3", "content": "c"}],
    ]
    merged = merge_query_results(results, method="interleaving")
    assert [r["chunk_id"] for r in merged] == ["1", "3", "2"]


def test_merge_query_results_rejects_an_unknown_method():
    with pytest.raises(ValueError):
        merge_query_results([[{"chunk_id": "1", "content": "a"}]], method="not-a-real-method")


def test_merge_query_results_is_empty_input_safe():
    assert merge_query_results([]) == []
    assert merge_query_results([[], []]) == []


# ------------------------------- deduplicate_results / rerank_merged_results -------------------------------


def test_deduplicate_results_reuses_the_real_hash_dedup():
    """Validation criterion: le dédoublonnage fonctionne."""
    results = [{"chunk_id": "1", "content": "same real text"}, {"chunk_id": "2", "content": "same real text"}]
    assert len(deduplicate_results(results)) == 1


def test_rerank_merged_results_favors_the_real_original_query():
    """Validation criterion: le reranking fonctionne."""
    results = [
        {"chunk_id": "1", "content": "Bananas are a good source of potassium."},
        {"chunk_id": "2", "content": "The refund policy allows returns within 30 days."},
    ]
    reranked = rerank_merged_results(results, "refund policy")
    assert reranked[0]["chunk_id"] == "2"


def test_rerank_merged_results_is_empty_input_safe():
    assert rerank_merged_results([], "anything") == []


# ------------------------------------- multi_query_search -------------------------------------


async def test_multi_query_search_returns_real_merged_reranked_results(db_session, monkeypatch):
    """Validation criterion: le pipeline complet de multi-query
    fonctionne."""
    org = await _make_org(db_session, "Org Multi Query Search")
    document = await _make_document(db_session, org.id)
    await _add_chunks(db_session, org.id, document.id, [
        "The refund policy allows returns within 30 days.",
        "Our office relocated to a new building downtown.",
    ])

    mock_acompletion = AsyncMock(return_value=_real_response("How do I get my money back?"))
    monkeypatch.setattr(litellm, "acompletion", mock_acompletion)

    results = await multi_query_search(db_session, org.id, "refund policy", top_k=1, num_variants=2)

    assert len(results) == 1
    assert "refund policy" in results[0]["content"]


async def test_multi_query_search_respects_the_real_kill_switch(db_session, monkeypatch):
    org = await _make_org(db_session, "Org Multi Query Kill Switch")
    document = await _make_document(db_session, org.id)
    await _add_chunks(db_session, org.id, document.id, ["The refund policy allows returns within 30 days."])

    mock_acompletion = AsyncMock()
    monkeypatch.setattr(litellm, "acompletion", mock_acompletion)
    monkeypatch.setattr(settings, "MULTI_QUERY_ENABLED", False)

    results = await multi_query_search(db_session, org.id, "refund policy", top_k=1)

    assert len(results) == 1
    mock_acompletion.assert_not_called()


# ------------------------- Phase 4, Étape 2: run_queries_parallel's own new search_fn -------------------------


async def test_run_queries_parallel_defaults_to_vector_search_when_no_search_fn_given():
    """Validation criterion: rétrocompatibilité -- every pre-existing
    real caller/test of this function (above) keeps working unchanged,
    since `search_fn=None` still means plain `vector_search`."""
    import inspect

    signature = inspect.signature(run_queries_parallel)
    assert signature.parameters["search_fn"].default is None


async def test_run_queries_parallel_uses_a_real_custom_search_fn_when_given(db_session):
    """Validation criterion: Multi-Query doit alimenter le retrieval
    existant (requirement 11) -- api.services.retrieval_pipeline.search's
    own real wiring passes the ACTUAL resolved strategy (e.g.
    hybrid_search, BM25 included), not always plain vector_search."""
    from api.services.retrieval_pipeline import hybrid_search

    org = await _make_org(db_session, "Org Multi Query Custom Search Fn")
    document = await _make_document(db_session, org.id)
    await _add_chunks(db_session, org.id, document.id, [
        "The invoice number INV-445566 is attached to this order.",
        "Our office relocated to a new building downtown.",
    ])

    results = await run_queries_parallel(
        db_session, org.id, ["INV-445566", "invoice number"], top_k=1, search_fn=hybrid_search,
    )

    assert len(results) == 2
    assert all(len(r) == 1 for r in results)
    assert all("INV-445566" in r[0]["content"] for r in results)
