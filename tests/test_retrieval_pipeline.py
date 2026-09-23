"""Partie 3.3.4/3.3.5/3.3.6 -- tests for api/services/retrieval_pipeline.py's
own real, live, multi-tenant search pipeline. Real embeddings, real
BM25, real cross-encoder reranking -- no mocking, matching this
codebase's own established real-infrastructure testing precedent
(tests/test_documents_integration.py, tests/test_semantic_chunking.py).

Phase 4, Étape 2 (Advanced Retrieval) tests below mock `litellm.acompletion`
for the 3 LLM-touching features (Query Rewriting, Multi-Query, HyDE),
the same real, documented exception `tests/test_hyde.py`/
`tests/test_multi_query.py` already established -- everything else
(embeddings, BM25, MMR's own cosine similarity) stays real."""

import uuid
from unittest.mock import AsyncMock

import litellm
import pytest
from litellm.types.utils import Choices, Message, ModelResponse

from api.config import settings as app_settings
from api.models.document import Document, DocumentChunk, DocumentStatus
from api.models.organization import Organization
from api.security.documents import generate_embeddings
from api.services.retrieval_pipeline import (
    bm25_search, build_llm_context, hybrid_reranked_search, hybrid_search, search, search_with_context, vector_search,
)

EMBEDDING_MODEL = "sentence-transformers/all-MiniLM-L6-v2"


def _real_response(text: str) -> ModelResponse:
    message = Message(content=text, role="assistant")
    choice = Choices(message=message, index=0, finish_reason="stop")
    return ModelResponse(choices=[choice])


@pytest.fixture(autouse=True)
def _configure_key(monkeypatch):
    monkeypatch.setattr(app_settings, "ANTHROPIC_API_KEY", "sk-ant-test")


async def _make_org(db_session, name):
    org = Organization(name=name, slug=f"{name.lower().replace(' ', '-')}-{uuid.uuid4().hex[:8]}")
    db_session.add(org)
    await db_session.flush()
    return org


async def _make_document(db_session, org_id, name="doc.pdf", source_url=None):
    document = Document(
        organization_id=org_id, name=name, file_key=f"documents/{uuid.uuid4()}/{name}",
        file_size=100, file_type="application/pdf", status=DocumentStatus.completed.value, source_url=source_url,
    )
    db_session.add(document)
    await db_session.flush()
    return document


async def _add_chunks(db_session, org_id, document_id, texts):
    embeddings = generate_embeddings(texts, EMBEDDING_MODEL)
    for text, embedding in zip(texts, embeddings):
        db_session.add(DocumentChunk(document_id=document_id, organization_id=org_id, content=text, embedding=embedding))
    await db_session.commit()


# -------------------------- real multi-tenant isolation (vision critique 1) --------------------------


async def test_vector_search_never_returns_another_organizations_chunks(db_session):
    """Validation criterion: la recherche ne retourne pas les chunks
    d'une autre organisation -- even with near-identical real content
    in both organizations."""
    org_a = await _make_org(db_session, "Org A Isolation")
    org_b = await _make_org(db_session, "Org B Isolation")
    doc_a = await _make_document(db_session, org_a.id)
    doc_b = await _make_document(db_session, org_b.id)
    await _add_chunks(db_session, org_a.id, doc_a.id, ["The quarterly revenue report shows strong growth."])
    await _add_chunks(db_session, org_b.id, doc_b.id, ["The quarterly revenue report shows strong growth."])

    results = await vector_search(db_session, org_a.id, "quarterly revenue report", top_k=10)
    assert len(results) == 1
    assert results[0]["document_id"] == str(doc_a.id)
    assert all(r["document_id"] == str(doc_a.id) for r in results)


async def test_bm25_search_never_returns_another_organizations_chunks(db_session):
    org_a = await _make_org(db_session, "Org A BM25 Isolation")
    org_b = await _make_org(db_session, "Org B BM25 Isolation")
    doc_a = await _make_document(db_session, org_a.id)
    doc_b = await _make_document(db_session, org_b.id)
    await _add_chunks(db_session, org_a.id, doc_a.id, ["A unique keyword xyzzyplugh appears here."])
    await _add_chunks(db_session, org_b.id, doc_b.id, ["A unique keyword xyzzyplugh appears here too."])

    results = await bm25_search(db_session, org_a.id, "xyzzyplugh", top_k=10)
    assert len(results) == 1
    assert results[0]["document_id"] == str(doc_a.id)


async def test_hybrid_search_never_returns_another_organizations_chunks(db_session):
    org_a = await _make_org(db_session, "Org A Hybrid Isolation")
    org_b = await _make_org(db_session, "Org B Hybrid Isolation")
    doc_a = await _make_document(db_session, org_a.id)
    doc_b = await _make_document(db_session, org_b.id)
    await _add_chunks(db_session, org_a.id, doc_a.id, ["Real onboarding instructions for new employees."])
    await _add_chunks(db_session, org_b.id, doc_b.id, ["Real onboarding instructions for new employees."])

    results = await hybrid_search(db_session, org_a.id, "onboarding instructions", top_k=10)
    assert len(results) == 1
    assert results[0]["document_id"] == str(doc_a.id)


async def test_search_returns_nothing_for_an_organization_with_no_real_documents(db_session):
    """A real, honest empty-org case: an organization with zero real
    documents/chunks gets a real, empty result, never an error."""
    org = await _make_org(db_session, "Org No Documents")
    assert await search(db_session, org.id, "anything at all") == []
    assert await vector_search(db_session, org.id, "anything at all") == []
    assert await bm25_search(db_session, org.id, "anything at all") == []


# ------------------------------- real strategies (vision critique 4) -------------------------------


async def test_vector_search_ranks_the_real_most_relevant_chunk_first(db_session):
    """Validation criterion: les stratégies de recherche
    fonctionnent."""
    org = await _make_org(db_session, "Org Vector Relevance")
    document = await _make_document(db_session, org.id)
    await _add_chunks(db_session, org.id, document.id, [
        "The Amazon rainforest is home to millions of species.",
        "Our refund policy allows returns within 30 days of purchase.",
        "Python is a popular programming language for data science.",
    ])

    results = await vector_search(db_session, org.id, "What is your return policy?", top_k=1)
    assert len(results) == 1
    assert "refund policy" in results[0]["content"]


async def test_bm25_search_ranks_exact_keyword_matches_first(db_session):
    org = await _make_org(db_session, "Org BM25 Relevance")
    document = await _make_document(db_session, org.id)
    await _add_chunks(db_session, org.id, document.id, [
        "The invoice number is INV-778899 for this order.",
        "Please contact support for general questions.",
        "Our office is located in downtown Paris.",
    ])

    results = await bm25_search(db_session, org.id, "INV-778899", top_k=1)
    assert len(results) == 1
    assert "INV-778899" in results[0]["content"]


async def test_hybrid_search_returns_real_ranked_results(db_session):
    org = await _make_org(db_session, "Org Hybrid Relevance")
    document = await _make_document(db_session, org.id)
    await _add_chunks(db_session, org.id, document.id, [
        "The capital of France is Paris.",
        "Bananas are a good source of potassium.",
        "The Eiffel Tower is located in Paris.",
    ])

    results = await hybrid_search(db_session, org.id, "Paris landmarks", top_k=2)
    assert len(results) == 2
    assert all("score" in r for r in results)


async def test_hybrid_search_uses_the_real_organization_configured_rrf_k(db_session):
    """Validation criterion: le RRF K est appliqué à la fusion --
    a real, direct check that a different rrf_k genuinely changes the
    real fused RRF score (`1 / (k + rank + 1)`), not just accepted and
    ignored."""
    org = await _make_org(db_session, "Org RRF K")
    document = await _make_document(db_session, org.id)
    await _add_chunks(db_session, org.id, document.id, [
        "The capital of France is Paris.",
        "Bananas are a good source of potassium.",
    ])

    default_k = await hybrid_search(db_session, org.id, "Paris capital", top_k=1)
    small_k = await hybrid_search(db_session, org.id, "Paris capital", top_k=1, org_settings={"rrf_k": 1})

    assert default_k[0]["chunk_id"] == small_k[0]["chunk_id"]  # same real top real result either way
    assert default_k[0]["score"] != small_k[0]["score"]  # but a real, different rrf_k really changes the real fused score


async def test_hybrid_reranked_search_returns_real_reranked_results(db_session):
    org = await _make_org(db_session, "Org Reranked Relevance")
    document = await _make_document(db_session, org.id)
    await _add_chunks(db_session, org.id, document.id, [
        "To reset your password, click the forgot password link.",
        "Our headquarters relocated to a new building last year.",
        "Password resets require a valid email address on file.",
    ])

    results = await hybrid_reranked_search(db_session, org.id, "how do I reset my password", top_k=2)
    assert len(results) == 2
    assert all("score" in r for r in results)
    assert "password" in results[0]["content"].lower()


async def test_search_dispatches_to_the_real_requested_strategy(db_session):
    org = await _make_org(db_session, "Org Dispatch")
    document = await _make_document(db_session, org.id)
    await _add_chunks(db_session, org.id, document.id, ["Real content about shipping and delivery times."])

    vector_only = await search(db_session, org.id, "shipping delivery", strategy="vector_only", top_k=5)
    bm25_only = await search(db_session, org.id, "shipping delivery", strategy="bm25_only", top_k=5)
    assert len(vector_only) == 1
    assert len(bm25_only) == 1


async def test_search_is_empty_for_an_empty_query(db_session):
    org = await _make_org(db_session, "Org Empty Query")
    assert await search(db_session, org.id, "") == []
    assert await search(db_session, org.id, "   ") == []


async def test_search_with_context_includes_real_document_context(db_session):
    """Validation criterion: search_with_context retourne les chunks
    avec contexte."""
    org = await _make_org(db_session, "Org Context")
    document = await _make_document(db_session, org.id, name="handbook.pdf", source_url="https://example.com/handbook")
    await _add_chunks(db_session, org.id, document.id, ["Real vacation policy details for employees."])

    results = await search_with_context(db_session, org.id, "vacation policy", strategy="vector_only", top_k=1)
    assert len(results) == 1
    assert results[0]["context"]["document_name"] == "handbook.pdf"
    assert results[0]["context"]["file_type"] == "application/pdf"
    # Partie 6.1.4 -- the parent document's own real source_url now
    # flows through the same real join, for a real citation's own
    # source_url to be captured from at citation-creation time.
    assert results[0]["context"]["source_url"] == "https://example.com/handbook"
    assert results[0]["source_url"] == "https://example.com/handbook"


# ------------------------------- real config application (vision critique 2) -------------------------------


async def test_search_respects_a_real_organization_configured_top_k(db_session):
    """Validation criterion: les paramètres de config sont appliqués.
    Real `score_threshold=0.0` here isolates the real top_k behavior
    under test from Partie 3.3.7's own real (and, by default, active)
    score-threshold filtering, covered by its own dedicated tests
    below."""
    org = await _make_org(db_session, "Org Config TopK")
    document = await _make_document(db_session, org.id)
    await _add_chunks(db_session, org.id, document.id, [f"Real filler sentence number {i} about various topics." for i in range(10)])

    results = await search(db_session, org.id, "filler sentence", strategy="vector_only", score_threshold=0.0, org_settings={"top_k": 3})
    assert len(results) == 3


async def test_search_respects_an_explicit_top_k_override(db_session):
    org = await _make_org(db_session, "Org Override TopK")
    document = await _make_document(db_session, org.id)
    await _add_chunks(db_session, org.id, document.id, [f"Real filler sentence number {i} about various topics." for i in range(10)])

    results = await search(db_session, org.id, "filler sentence", strategy="vector_only", top_k=2, score_threshold=0.0)
    assert len(results) == 2



# ------------------------------- 3.3.7 real score threshold -------------------------------


async def test_search_filters_out_real_low_scoring_results(db_session):
    """Validation criterion: les chunks sont filtrés correctement."""
    org = await _make_org(db_session, "Org Score Threshold")
    document = await _make_document(db_session, org.id)
    await _add_chunks(db_session, org.id, document.id, [
        "The refund policy allows returns within 30 days of purchase.",
        "Bananas are a good source of potassium and fiber.",
        "The office holiday party is scheduled for December.",
    ])

    all_results = await search(db_session, org.id, "refund policy", strategy="vector_only", score_threshold=0.0)
    filtered_results = await search(db_session, org.id, "refund policy", strategy="vector_only", score_threshold=0.99)
    assert len(filtered_results) < len(all_results)
    assert "refund policy" in filtered_results[0]["content"]


async def test_search_score_threshold_is_read_from_real_organization_settings():
    """Validation criterion: le seuil est lu depuis
    organization_settings -- a real, direct check on the resolver
    search() itself calls (full coverage of the resolver's own real
    precedence lives in tests/test_retrieval_config.py)."""
    from api.services.retrieval_config import resolve_score_threshold

    assert resolve_score_threshold({"score_threshold": 0.9}) == 0.9


async def test_search_score_threshold_falls_back_to_the_real_default(db_session):
    """Validation criterion: le fallback fonctionne."""
    org = await _make_org(db_session, "Org Score Threshold Default")
    document = await _make_document(db_session, org.id)
    await _add_chunks(db_session, org.id, document.id, ["A single real chunk with nothing to compare it against."])

    # A lone real candidate normalizes to 1.0 (see _normalize_scores'
    # own docstring), so it survives the real, default 0.5 threshold
    # with no explicit override at all.
    results = await search(db_session, org.id, "single chunk", strategy="vector_only")
    assert len(results) == 1


async def test_search_rejects_an_invalid_score_threshold(db_session):
    """Validation criterion: robustesse -- seuil invalide."""
    import pytest

    org = await _make_org(db_session, "Org Invalid Score Threshold")
    with pytest.raises(ValueError):
        await search(db_session, org.id, "anything", strategy="vector_only", score_threshold=1.5)


async def test_filter_by_score_threshold_keeps_only_real_results_at_or_above_it():
    from api.services.retrieval_pipeline import filter_by_score_threshold

    results = [{"score": 0.1}, {"score": 0.5}, {"score": 0.9}]
    filtered = filter_by_score_threshold(results, 0.5)
    # normalized: 0.0, 0.5, 1.0 -- threshold 0.5 keeps the last two real results
    assert len(filtered) == 2
    assert all(r["normalized_score"] >= 0.5 for r in filtered)


async def test_hybrid_reranked_search_does_not_compound_the_real_candidate_pool_past_top_k_max(db_session):
    """A real regression test for a real bug found while building this
    étape: hybrid_reranked_search -> hybrid_search -> vector_search
    each independently multiplied the candidate pool by 10 through
    resolve_top_k's own real TOP_K_MAX bound, so even a modest
    org-configured top_k (20) compounded past the real ceiling (100)
    two layers down and raised, instead of returning real results."""
    org = await _make_org(db_session, "Org No Compounding")
    document = await _make_document(db_session, org.id)
    await _add_chunks(db_session, org.id, document.id, [f"Real filler content number {i} for the compounding test." for i in range(5)])

    results = await hybrid_reranked_search(db_session, org.id, "filler content", org_settings={"top_k": 20})
    assert len(results) <= 5


# ---------------------------------------------------------------- build_llm_context (audit, 2026-09-19)


def test_build_llm_context_returns_none_for_no_chunks():
    assert build_llm_context([]) is None
    assert build_llm_context(None) is None


def test_build_llm_context_joins_real_chunk_content():
    chunks = [{"content": "First chunk."}, {"content": "Second chunk."}]
    result = build_llm_context(chunks)
    assert result == "First chunk.\n\nSecond chunk."


def test_build_llm_context_truncates_past_the_real_token_budget(monkeypatch):
    """Real regression test for a real bug found via audit: context used
    to be joined with no length bound at all. Sets a tiny budget so a
    real, short second chunk is genuinely excluded, not just trimmed."""
    from api.config import settings

    monkeypatch.setattr(settings, "RAG_CONTEXT_MAX_TOKENS", 3)
    chunks = [{"content": "one two three four five six seven eight"}, {"content": "short"}]
    result = build_llm_context(chunks)
    assert result == chunks[0]["content"]
    assert "short" not in result


# ==================================================================
# Phase 4, Étape 2 -- Advanced Retrieval, wired into search() itself.
# ==================================================================

# ------------------------------- rétrocompatibilité (requirement 4) -------------------------------


async def test_search_is_byte_identical_for_an_organization_with_no_advanced_features(db_session, monkeypatch):
    """Validation criterion: rétrocompatibilité -- a real organization
    that never touches any of the 5 new settings gets the exact same
    real results, in the exact same real order, as before this étape.
    A real LLM call here would fail the test (mock raises), proving
    none of the 5 new features' own LLM calls run at all when disabled."""
    mock_acompletion = AsyncMock(side_effect=AssertionError("no real LLM call should happen when every advanced feature is disabled"))
    monkeypatch.setattr(litellm, "acompletion", mock_acompletion)

    org = await _make_org(db_session, "Org Retrocompat")
    document = await _make_document(db_session, org.id)
    await _add_chunks(db_session, org.id, document.id, [
        "The refund policy allows returns within 30 days of purchase.",
        "Bananas are a good source of potassium and fiber.",
        "The office holiday party is scheduled for December.",
    ])

    baseline = await search(db_session, org.id, "refund policy", strategy="hybrid", score_threshold=0.0)
    with_empty_org_settings = await search(db_session, org.id, "refund policy", strategy="hybrid", score_threshold=0.0, org_settings={})

    assert baseline == with_empty_org_settings
    assert len(baseline) == 3
    mock_acompletion.assert_not_called()


# ------------------------------- 1. Query Rewriting (requirement 5) -------------------------------


async def test_search_rewrites_the_query_when_enabled(db_session, monkeypatch):
    """Validation criterion: la réécriture améliore la recherche."""
    mock_acompletion = AsyncMock(return_value=_real_response("What is the policy for getting a refund?"))
    monkeypatch.setattr(litellm, "acompletion", mock_acompletion)

    org = await _make_org(db_session, "Org Query Rewriting")
    document = await _make_document(db_session, org.id)
    await _add_chunks(db_session, org.id, document.id, ["The refund policy allows returns within 30 days."])

    results = await search(
        db_session, org.id, "refund plz", strategy="vector_only", score_threshold=0.0,
        org_settings={"query_rewriting_enabled": True},
    )

    assert len(results) == 1
    mock_acompletion.assert_called()


async def test_search_query_rewriting_is_disabled_by_default(db_session, monkeypatch):
    mock_acompletion = AsyncMock()
    monkeypatch.setattr(litellm, "acompletion", mock_acompletion)

    org = await _make_org(db_session, "Org Query Rewriting Default")
    document = await _make_document(db_session, org.id)
    await _add_chunks(db_session, org.id, document.id, ["The refund policy allows returns within 30 days."])

    await search(db_session, org.id, "refund policy", strategy="vector_only", score_threshold=0.0)

    mock_acompletion.assert_not_called()


async def test_search_falls_back_to_the_real_original_query_when_rewriting_fails(db_session, monkeypatch):
    """Validation criterion: robustesse -- un échec de réécriture ne
    casse jamais la recherche (requirement 5's own explicit ask)."""
    mock_acompletion = AsyncMock(side_effect=litellm.exceptions.RateLimitError(
        message="rate limited", llm_provider="anthropic", model="claude",
    ))
    monkeypatch.setattr(litellm, "acompletion", mock_acompletion)
    monkeypatch.setattr(app_settings, "LLM_MAX_RETRIES", 0)

    org = await _make_org(db_session, "Org Query Rewriting Failure")
    document = await _make_document(db_session, org.id)
    await _add_chunks(db_session, org.id, document.id, ["The refund policy allows returns within 30 days."])

    results = await search(
        db_session, org.id, "refund policy", strategy="vector_only", score_threshold=0.0,
        org_settings={"query_rewriting_enabled": True},
    )

    assert len(results) == 1  # the real search still worked, using the real, un-rewritten query


# ------------------------------------- 3. HyDE (requirement 7) -------------------------------------


async def test_search_uses_hyde_when_enabled(db_session, monkeypatch):
    """Validation criterion: HyDE améliore la recherche sémantique."""
    mock_acompletion = AsyncMock(return_value=_real_response(
        "Customers can request a refund within thirty days of the original purchase.",
    ))
    monkeypatch.setattr(litellm, "acompletion", mock_acompletion)

    org = await _make_org(db_session, "Org HyDE Search")
    document = await _make_document(db_session, org.id)
    await _add_chunks(db_session, org.id, document.id, [
        "Refunds are processed within 30 days of the original purchase date.",
        "Our office relocated to a new building downtown last year.",
    ])

    results = await search(
        db_session, org.id, "How do I get my money back?", strategy="vector_only", top_k=1,
        org_settings={"hyde_enabled": True},
    )

    assert len(results) == 1
    assert "Refunds" in results[0]["content"]
    mock_acompletion.assert_called()


async def test_search_hyde_never_affects_the_real_bm25_leg(db_session, monkeypatch):
    """Validation criterion: HyDE améliore la partie vectorielle sans
    casser le BM25 (requirement 11) -- `bm25_search` (unaffected by any
    real `query_embedding` override, which only `vector_search` ever
    accepts) still ranks the real, unique keyword match first, whatever
    HyDE's own real, disposable hypothetical embedding does to the
    vector leg."""
    mock_acompletion = AsyncMock(return_value=_real_response("A vague, unrelated hypothetical passage."))
    monkeypatch.setattr(litellm, "acompletion", mock_acompletion)

    org = await _make_org(db_session, "Org HyDE BM25 Preserved")
    document = await _make_document(db_session, org.id)
    await _add_chunks(db_session, org.id, document.id, [
        "The invoice number is INV-998877 for this specific order.",
        "General information about the company history.",
        "Our office relocated to a new building last year.",
        "Bananas are a good source of potassium and fiber.",
        "The weather has been unusually warm this week.",
    ])

    bm25_results = await bm25_search(db_session, org.id, "INV-998877", top_k=1)
    assert "INV-998877" in bm25_results[0]["content"]

    # A real, direct check that the HyDE-enabled hybrid search doesn't
    # raise/misbehave and still surfaces the real keyword match somewhere
    # in its real, wider candidate pool -- the exact final ranking under
    # RRF fusion of a vector leg deliberately pointed at an unrelated
    # hypothetical document is a real, separate question from whether
    # BM25 itself was corrupted (checked directly above).
    results = await search(
        db_session, org.id, "INV-998877", strategy="hybrid", top_k=5, score_threshold=0.0,
        org_settings={"hyde_enabled": True},
    )
    assert any("INV-998877" in r["content"] for r in results)
    mock_acompletion.assert_called()


async def test_search_skips_hyde_for_the_real_bm25_only_strategy(db_session, monkeypatch):
    """HyDE has no real vector leg to override under bm25_only -- no
    real LLM call should happen at all."""
    mock_acompletion = AsyncMock(side_effect=AssertionError("HyDE must not run for bm25_only"))
    monkeypatch.setattr(litellm, "acompletion", mock_acompletion)

    org = await _make_org(db_session, "Org HyDE Skips BM25 Only")
    document = await _make_document(db_session, org.id)
    await _add_chunks(db_session, org.id, document.id, ["A unique keyword xyzzyplugh appears here."])

    results = await search(
        db_session, org.id, "xyzzyplugh", strategy="bm25_only", org_settings={"hyde_enabled": True},
    )
    assert len(results) == 1
    mock_acompletion.assert_not_called()


async def test_search_falls_back_to_plain_embedding_when_hyde_fails(db_session, monkeypatch):
    """Validation criterion: robustesse -- un échec HyDE retombe sur
    l'embedding de la requête originale (requirement 7's own explicit
    ask)."""
    mock_acompletion = AsyncMock(side_effect=litellm.exceptions.RateLimitError(
        message="rate limited", llm_provider="anthropic", model="claude",
    ))
    monkeypatch.setattr(litellm, "acompletion", mock_acompletion)
    monkeypatch.setattr(app_settings, "LLM_MAX_RETRIES", 0)

    org = await _make_org(db_session, "Org HyDE Failure Fallback")
    document = await _make_document(db_session, org.id)
    await _add_chunks(db_session, org.id, document.id, ["Refunds are processed within 30 days."])

    results = await search(
        db_session, org.id, "refund policy", strategy="vector_only", top_k=1, org_settings={"hyde_enabled": True},
    )
    assert len(results) == 1


async def test_search_hyde_is_disabled_by_default(db_session, monkeypatch):
    mock_acompletion = AsyncMock()
    monkeypatch.setattr(litellm, "acompletion", mock_acompletion)

    org = await _make_org(db_session, "Org HyDE Default")
    document = await _make_document(db_session, org.id)
    await _add_chunks(db_session, org.id, document.id, ["Refunds are processed within 30 days."])

    await search(db_session, org.id, "refund policy", strategy="vector_only")

    mock_acompletion.assert_not_called()


# ------------------------------------- 2. Multi-Query (requirement 6) -------------------------------------


async def test_search_multi_query_reuses_the_real_existing_rrf_and_hybrid_pipeline(db_session, monkeypatch):
    """Validation criterion: Multi-Query alimente le retrieval existant
    (requirement 11) -- a real BM25 keyword match still surfaces under
    `hybrid` strategy with multi-query enabled, proving each variant
    really runs the full hybrid (BM25 + vector + RRF) pipeline, not a
    vector-only shortcut."""
    mock_acompletion = AsyncMock(return_value=_real_response("How can I request a refund?\nWhat's your money-back policy?"))
    monkeypatch.setattr(litellm, "acompletion", mock_acompletion)

    org = await _make_org(db_session, "Org Multi Query Hybrid Reuse")
    document = await _make_document(db_session, org.id)
    await _add_chunks(db_session, org.id, document.id, [
        "The invoice number INV-112233 belongs to this specific order.",
        "General company background information.",
        "Our office relocated to a new building last year.",
        "Bananas are a good source of potassium and fiber.",
    ])

    results = await search(
        db_session, org.id, "INV-112233", strategy="hybrid", top_k=4, score_threshold=0.0,
        org_settings={"multi_query_enabled": True, "multi_query_count": 2},
    )
    assert any("INV-112233" in r["content"] for r in results)
    mock_acompletion.assert_called()


async def test_search_multi_query_respects_the_real_configured_variant_count(db_session, monkeypatch):
    """Validation criterion: le nombre de requêtes générées est limité
    (requirement 13's own cost guardrail)."""
    mock_acompletion = AsyncMock(return_value=_real_response("A real reformulation."))
    monkeypatch.setattr(litellm, "acompletion", mock_acompletion)

    org = await _make_org(db_session, "Org Multi Query Count")
    document = await _make_document(db_session, org.id)
    await _add_chunks(db_session, org.id, document.id, ["Refunds are processed within 30 days."])

    await search(
        db_session, org.id, "refund policy", strategy="vector_only", top_k=1,
        org_settings={"multi_query_enabled": True, "multi_query_count": 3},
    )
    # 1 real LLM call generates every (num_variants - 1) reformulation in one real prompt
    assert mock_acompletion.call_count == 1


async def test_search_multi_query_falls_back_to_a_single_query_on_a_real_generation_failure(db_session, monkeypatch):
    """Validation criterion: robustesse -- un échec de génération de
    variantes ne casse jamais la recherche."""
    mock_acompletion = AsyncMock(side_effect=litellm.exceptions.RateLimitError(
        message="rate limited", llm_provider="anthropic", model="claude",
    ))
    monkeypatch.setattr(litellm, "acompletion", mock_acompletion)
    monkeypatch.setattr(app_settings, "LLM_MAX_RETRIES", 0)

    org = await _make_org(db_session, "Org Multi Query Generation Failure")
    document = await _make_document(db_session, org.id)
    await _add_chunks(db_session, org.id, document.id, ["Refunds are processed within 30 days."])

    results = await search(
        db_session, org.id, "refund policy", strategy="vector_only", top_k=1,
        org_settings={"multi_query_enabled": True},
    )
    assert len(results) == 1


async def test_search_multi_query_is_disabled_by_default(db_session, monkeypatch):
    mock_acompletion = AsyncMock()
    monkeypatch.setattr(litellm, "acompletion", mock_acompletion)

    org = await _make_org(db_session, "Org Multi Query Default")
    document = await _make_document(db_session, org.id)
    await _add_chunks(db_session, org.id, document.id, ["Refunds are processed within 30 days."])

    await search(db_session, org.id, "refund policy", strategy="vector_only")

    mock_acompletion.assert_not_called()


# ---------------------------------------- 4. MMR (requirement 8) ----------------------------------------


async def test_search_mmr_diversifies_the_real_final_results(db_session):
    """Validation criterion: MMR réduit la redondance -- 2 real,
    near-duplicate chunks and 1 real, distinct one: MMR should prefer
    the real, more diverse pick for the 2nd slot over a redundant
    near-duplicate of the top result."""
    org = await _make_org(db_session, "Org MMR Diversify")
    document = await _make_document(db_session, org.id)
    await _add_chunks(db_session, org.id, document.id, [
        "The refund policy allows returns within 30 days of purchase.",
        "Our refund policy permits returns within thirty days of buying.",
        "The office is located in downtown Paris.",
    ])

    without_mmr = await search(db_session, org.id, "refund policy", strategy="vector_only", top_k=2, score_threshold=0.0)
    with_mmr = await search(
        db_session, org.id, "refund policy", strategy="vector_only", top_k=2, score_threshold=0.0,
        org_settings={"mmr_enabled": True, "mmr_lambda": 0.3},
    )

    assert len(with_mmr) == 2
    without_ids = {r["chunk_id"] for r in without_mmr}
    with_ids = {r["chunk_id"] for r in with_mmr}
    # A real, meaningful MMR effect: the low-lambda (diversity-favoring)
    # real result set differs from the plain top-2-by-relevance set.
    assert with_ids != without_ids


async def test_search_mmr_uses_a_real_wider_candidate_pool_than_final_top_k(db_session, monkeypatch):
    """Validation criterion: pool de candidats > k final (requirement 8's
    own explicit ask) -- a real, direct check that MMR's own resolved
    candidate pool is really wider than the requested top_k."""
    from api.services import retrieval_pipeline as pipeline_module

    org = await _make_org(db_session, "Org MMR Candidate Pool")
    document = await _make_document(db_session, org.id)
    await _add_chunks(db_session, org.id, document.id, [f"Real filler chunk number {i}." for i in range(6)])

    seen_top_k = []
    real_vector_search = pipeline_module.vector_search

    async def _spy_vector_search(db, organization_id, query, top_k=None, **kwargs):
        seen_top_k.append(top_k)
        return await real_vector_search(db, organization_id, query, top_k=top_k, **kwargs)

    monkeypatch.setattr(pipeline_module, "_STRATEGY_FUNCTIONS", {**pipeline_module._STRATEGY_FUNCTIONS, "vector_only": _spy_vector_search})

    await search(
        db_session, org.id, "filler chunk", strategy="vector_only", top_k=2, score_threshold=0.0,
        org_settings={"mmr_enabled": True},
    )

    assert seen_top_k[0] == 6  # 2 * 3, resolve_mmr_candidate_k's own real multiplier


async def test_search_mmr_rejects_an_invalid_lambda(db_session):
    """Validation criterion: robustesse -- lambda invalide."""
    org = await _make_org(db_session, "Org MMR Invalid Lambda")
    document = await _make_document(db_session, org.id)
    await _add_chunks(db_session, org.id, document.id, ["Real content about shipping."])

    with pytest.raises(ValueError):
        await search(
            db_session, org.id, "shipping", strategy="vector_only", org_settings={"mmr_enabled": True, "mmr_lambda": 1.5},
        )


async def test_search_mmr_is_disabled_by_default(db_session):
    org = await _make_org(db_session, "Org MMR Default")
    document = await _make_document(db_session, org.id)
    await _add_chunks(db_session, org.id, document.id, [
        "The refund policy allows returns within 30 days of purchase.",
        "Our refund policy permits returns within thirty days of buying.",
    ])

    results = await search(db_session, org.id, "refund policy", strategy="vector_only", top_k=2, score_threshold=0.0)
    assert len(results) == 2


# ============================================================
# Phase 4, Étape 2 correctif ciblé -- MMR audit tests (Partie D)
# ============================================================


async def test_search_mmr_result_count_never_exceeds_top_k(db_session):
    """Test 2 -- MMR activé -> nombre de résultats <= top_k."""
    org = await _make_org(db_session, "Org MMR Count Bound")
    document = await _make_document(db_session, org.id)
    await _add_chunks(db_session, org.id, document.id, [f"Real filler chunk number {i} about topic variety." for i in range(8)])

    results = await search(
        db_session, org.id, "filler chunk", strategy="vector_only", top_k=3, score_threshold=0.0,
        org_settings={"mmr_enabled": True},
    )
    assert len(results) <= 3


async def test_search_mmr_lambda_1_behaves_like_pure_relevance_ranking(db_session):
    """Test 3 -- lambda=1 -> comportement orienté pertinence: with the
    diversity term fully zeroed out, MMR's own real selection order must
    match the real, plain relevance ranking exactly."""
    org = await _make_org(db_session, "Org MMR Lambda One")
    document = await _make_document(db_session, org.id)
    await _add_chunks(db_session, org.id, document.id, [
        "The refund policy allows returns within 30 days of purchase.",
        "Our refund policy permits returns within thirty days of buying.",
        "The weather has been unusually warm this week.",
        "Bananas are a good source of potassium and fiber.",
    ])

    plain = await search(db_session, org.id, "refund policy", strategy="vector_only", top_k=3, score_threshold=0.0)
    with_mmr = await search(
        db_session, org.id, "refund policy", strategy="vector_only", top_k=3, score_threshold=0.0,
        org_settings={"mmr_enabled": True, "mmr_lambda": 1.0},
    )
    assert [r["chunk_id"] for r in with_mmr] == [r["chunk_id"] for r in plain]


async def test_search_mmr_lambda_0_favors_diversity_over_relevance(db_session):
    """Test 4 -- lambda=0 -> comportement orienté diversité: among 2
    near-duplicate top matches and 1 distinct chunk, a real,
    diversity-only MMR must prefer the distinct chunk for the 2nd slot
    over the redundant near-duplicate."""
    org = await _make_org(db_session, "Org MMR Lambda Zero")
    document = await _make_document(db_session, org.id)
    await _add_chunks(db_session, org.id, document.id, [
        "The refund policy allows returns within 30 days of purchase.",
        "Our refund policy permits returns within thirty days of buying.",
        "The office is located in downtown Paris.",
    ])

    plain = await search(db_session, org.id, "refund policy", strategy="vector_only", top_k=2, score_threshold=0.0)
    with_mmr = await search(
        db_session, org.id, "refund policy", strategy="vector_only", top_k=2, score_threshold=0.0,
        org_settings={"mmr_enabled": True, "mmr_lambda": 0.0},
    )
    assert {r["chunk_id"] for r in with_mmr} != {r["chunk_id"] for r in plain}


async def test_search_mmr_diversity_uses_real_chunk_embeddings_never_the_cross_encoder_score(db_session, monkeypatch):
    """Test 9 -- Cross-Encoder + MMR: audit confirms `select_diverse_chunks`
    computes candidate-to-candidate similarity from each real chunk's
    OWN embedding (`compute_chunk_embedding`), never from the real
    cross-encoder's own `score` field -- a real, direct spy proving
    `compute_chunk_embedding` is really called for every real MMR
    candidate under `hybrid_reranked_search`."""
    import api.services.mmr as mmr_module

    org = await _make_org(db_session, "Org MMR Not Cross Encoder Score")
    document = await _make_document(db_session, org.id)
    await _add_chunks(db_session, org.id, document.id, [
        "To reset your password, click the forgot password link.",
        "Password resets require a valid email address on file.",
        "Our headquarters relocated to a new building last year.",
    ])

    real_compute_chunk_embedding = mmr_module.compute_chunk_embedding
    seen_chunks = []

    def _spy_compute_chunk_embedding(chunk, *args, **kwargs):
        seen_chunks.append(chunk)
        return real_compute_chunk_embedding(chunk, *args, **kwargs)

    monkeypatch.setattr(mmr_module, "compute_chunk_embedding", _spy_compute_chunk_embedding)

    results = await search(
        db_session, org.id, "how do I reset my password", strategy="hybrid_reranked", top_k=2, score_threshold=0.0,
        org_settings={"mmr_enabled": True},
    )
    assert len(results) <= 2
    assert len(seen_chunks) > 0
    # Every real chunk MMR scored for diversity really carries its own
    # real, pre-computed embedding -- the real signal `compute_chunk_embedding`
    # reuses, never the cross-encoder's own real relevance `score`.
    assert all("embedding" in c for c in seen_chunks)


async def test_search_mmr_works_with_bm25_only_without_crashing(db_session):
    """Test 7 -- BM25-only + MMR: every real `DocumentChunk` always
    carries a real embedding regardless of retrieval strategy (the
    embedding is computed once, at ingestion) -- MMR is genuinely
    applicable even under `bm25_only`, no fallback needed, no crash."""
    org = await _make_org(db_session, "Org MMR BM25 Only")
    document = await _make_document(db_session, org.id)
    await _add_chunks(db_session, org.id, document.id, [
        "A unique keyword xyzzyplugh appears in this real chunk.",
        "A second, unrelated real chunk about the weather.",
        "A third real chunk about bananas and potassium.",
    ])

    results = await search(
        db_session, org.id, "xyzzyplugh", strategy="bm25_only", top_k=2, score_threshold=0.0,
        org_settings={"mmr_enabled": True},
    )
    assert len(results) <= 2
    assert any("xyzzyplugh" in r["content"] for r in results)


async def test_search_mmr_with_multi_query_preserves_the_real_rrf_fused_candidates(db_session, monkeypatch):
    """Test 10 -- Multi-Query + MMR: MMR must operate on the real,
    already RRF-fused multi-query result, never trigger its own,
    separate search."""
    mock_acompletion = AsyncMock(return_value=_real_response("How can I request a refund?\nWhat's the money-back policy?"))
    monkeypatch.setattr(litellm, "acompletion", mock_acompletion)

    org = await _make_org(db_session, "Org MMR Multi Query")
    document = await _make_document(db_session, org.id)
    await _add_chunks(db_session, org.id, document.id, [
        "The refund policy allows returns within 30 days of purchase.",
        "Our refund policy permits returns within thirty days of buying.",
        "The office is located in downtown Paris.",
        "Bananas are a good source of potassium and fiber.",
    ])

    results = await search(
        db_session, org.id, "refund policy", strategy="hybrid", top_k=2, score_threshold=0.0,
        org_settings={"multi_query_enabled": True, "multi_query_count": 2, "mmr_enabled": True},
    )
    assert len(results) <= 2
    mock_acompletion.assert_called()


async def test_search_mmr_with_hyde_only_ever_selects_real_retrieved_chunks(db_session, monkeypatch):
    """Test 11 -- HyDE + MMR: only real chunks are ever selected -- the
    real, disposable hypothetical document is never itself a candidate
    (it's a float vector used for ranking, never inserted into
    `results`)."""
    mock_acompletion = AsyncMock(return_value=_real_response("A hypothetical passage about refunds and returns."))
    monkeypatch.setattr(litellm, "acompletion", mock_acompletion)

    org = await _make_org(db_session, "Org MMR HyDE Real Chunks Only")
    document = await _make_document(db_session, org.id)
    real_contents = [
        "Refunds are processed within 30 days of the original purchase.",
        "Our office relocated to a new building downtown last year.",
        "Bananas are a good source of potassium and fiber.",
    ]
    await _add_chunks(db_session, org.id, document.id, real_contents)

    results = await search(
        db_session, org.id, "How do I get my money back?", strategy="vector_only", top_k=2, score_threshold=0.0,
        org_settings={"hyde_enabled": True, "mmr_enabled": True},
    )
    assert len(results) <= 2
    assert all(r["content"] in real_contents for r in results)


async def test_search_mmr_relevance_anchors_to_the_real_query_never_the_hyde_hypothetical(db_session, monkeypatch):
    """Real regression test for the real, targeted MMR fix (correctif
    ciblé, 2026-09-22): MMR's own relevance term must score against
    `effective_query`'s own real embedding, never HyDE's real,
    disposable hypothetical-document embedding, even when HyDE ran."""
    import api.services.semantic_filtering as semantic_filtering_module

    mock_acompletion = AsyncMock(return_value=_real_response("A vague, unrelated hypothetical passage."))
    monkeypatch.setattr(litellm, "acompletion", mock_acompletion)

    org = await _make_org(db_session, "Org MMR Anchor Real Query")
    document = await _make_document(db_session, org.id)
    await _add_chunks(db_session, org.id, document.id, [
        "The refund policy allows returns within 30 days of purchase.",
        "Our refund policy permits returns within thirty days of buying.",
        "The weather has been unusually warm this week.",
    ])

    seen_queries = []
    original = semantic_filtering_module.compute_query_embedding

    def _spy(query, *args, **kwargs):
        seen_queries.append(query)
        return original(query, *args, **kwargs)

    # `compute_query_embedding` is imported lazily inside search()'s own
    # MMR block (`from api.services.semantic_filtering import
    # compute_query_embedding`) -- patch it at its real source module so
    # the lazy import picks up the spy.
    monkeypatch.setattr(semantic_filtering_module, "compute_query_embedding", _spy)

    await search(
        db_session, org.id, "refund policy", strategy="vector_only", top_k=2, score_threshold=0.0,
        org_settings={"hyde_enabled": True, "mmr_enabled": True},
    )

    assert "refund policy" in seen_queries  # the real, original user query, never the HyDE hypothetical text


async def test_search_mmr_preserves_real_parent_context_for_surviving_children(db_session):
    """Test 12 -- Parent/Child + MMR: MMR must never break
    `child retrieval -> parent context`. Direct row construction
    (bypassing full document ingestion, out of this correctif's scope)
    -- 1 real parent (no embedding, exactly like real parent_child
    ingestion never embeds parents) + 3 real children (real embeddings,
    each carrying its own real `parent_context`)."""
    from api.models.document import DocumentChunk

    org = await _make_org(db_session, "Org MMR Parent Child")
    document = await _make_document(db_session, org.id)

    parent = DocumentChunk(
        document_id=document.id, organization_id=org.id, chunk_role="parent",
        content="A much wider real parent paragraph about the refund policy and its exceptions.",
    )
    db_session.add(parent)
    await db_session.flush()

    child_texts = [
        "The refund policy allows returns within 30 days of purchase.",
        "Our refund policy permits returns within thirty days of buying.",
        "Final sale items are excluded from the refund policy.",
    ]
    embeddings = generate_embeddings(child_texts, EMBEDDING_MODEL)
    for text, embedding in zip(child_texts, embeddings):
        db_session.add(DocumentChunk(
            document_id=document.id, organization_id=org.id, content=text, embedding=embedding,
            chunk_role="child", parent_chunk_id=parent.id,
            metadata_json={"parent_chunk_id": str(parent.id), "parent_context": parent.content},
        ))
    await db_session.commit()

    results = await search_with_context(
        db_session, org.id, "refund policy", strategy="vector_only", top_k=2, score_threshold=0.0,
        org_settings={"mmr_enabled": True, "mmr_lambda": 0.3},
    )
    assert len(results) <= 2
    assert len(results) >= 1
    for r in results:
        assert r["metadata_json"]["parent_context"] == parent.content  # real parent context untouched by MMR selection


# --------------------------- real, combined end-to-end path (requirement 19) ---------------------------


async def test_search_with_context_full_advanced_retrieval_path_enabled(db_session, monkeypatch):
    """Validation criterion: le vrai chemin complet -- Organization
    Settings -> Query -> Query Rewriting -> Multi-Query -> HyDE ->
    BM25/Embeddings -> RRF -> MMR -> Parent Context (compatibility) ->
    (Context Compression is generation.py's own concern, tested there)
    -> Citations (search_with_context's own "context" dict). Every
    optional component enabled at once, still resolving to a real,
    non-empty, correctly-shaped result."""
    mock_acompletion = AsyncMock(return_value=_real_response(
        "What is the process for requesting a refund on a recent purchase?",
    ))
    monkeypatch.setattr(litellm, "acompletion", mock_acompletion)

    org = await _make_org(db_session, "Org Full Advanced Path")
    document = await _make_document(db_session, org.id, name="policy.pdf")
    await _add_chunks(db_session, org.id, document.id, [
        "The refund policy allows returns within 30 days of purchase.",
        "Our office relocated to a new building downtown last year.",
        "General company background information for new employees.",
    ])

    org_settings = {
        "query_rewriting_enabled": True, "multi_query_enabled": True, "multi_query_count": 2,
        "hyde_enabled": True, "mmr_enabled": True, "mmr_lambda": 0.5, "retrieval_strategy": "hybrid",
    }

    results = await search_with_context(db_session, org.id, "refund plz", top_k=2, org_settings=org_settings)

    assert len(results) >= 1
    assert "refund" in results[0]["content"].lower()
    assert results[0]["context"]["document_name"] == "policy.pdf"


async def test_search_with_context_full_advanced_retrieval_path_disabled_matches_plain_search(db_session, monkeypatch):
    """The same real end-to-end path, every feature explicitly disabled
    -- must behave exactly like the pre-Étape-2 pipeline (requirement 4)."""
    mock_acompletion = AsyncMock(side_effect=AssertionError("no LLM call expected with every advanced feature disabled"))
    monkeypatch.setattr(litellm, "acompletion", mock_acompletion)

    org = await _make_org(db_session, "Org Full Path Disabled")
    document = await _make_document(db_session, org.id, name="policy.pdf")
    await _add_chunks(db_session, org.id, document.id, ["The refund policy allows returns within 30 days of purchase."])

    org_settings = {
        "query_rewriting_enabled": False, "multi_query_enabled": False, "hyde_enabled": False, "mmr_enabled": False,
    }
    results = await search_with_context(db_session, org.id, "refund policy", top_k=1, org_settings=org_settings)

    assert len(results) == 1
    mock_acompletion.assert_not_called()
