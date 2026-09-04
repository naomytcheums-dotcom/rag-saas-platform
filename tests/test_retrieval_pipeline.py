"""Partie 3.3.4/3.3.5/3.3.6 -- tests for api/services/retrieval_pipeline.py's
own real, live, multi-tenant search pipeline. Real embeddings, real
BM25, real cross-encoder reranking -- no mocking, matching this
codebase's own established real-infrastructure testing precedent
(tests/test_documents_integration.py, tests/test_semantic_chunking.py)."""

import uuid

from api.models.document import Document, DocumentChunk, DocumentStatus
from api.models.organization import Organization
from api.security.documents import generate_embeddings
from api.services.retrieval_pipeline import bm25_search, hybrid_reranked_search, hybrid_search, search, search_with_context, vector_search

EMBEDDING_MODEL = "sentence-transformers/all-MiniLM-L6-v2"


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
    document = await _make_document(db_session, org.id, name="handbook.pdf")
    await _add_chunks(db_session, org.id, document.id, ["Real vacation policy details for employees."])

    results = await search_with_context(db_session, org.id, "vacation policy", strategy="vector_only", top_k=1)
    assert len(results) == 1
    assert results[0]["context"]["document_name"] == "handbook.pdf"
    assert results[0]["context"]["file_type"] == "application/pdf"


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
