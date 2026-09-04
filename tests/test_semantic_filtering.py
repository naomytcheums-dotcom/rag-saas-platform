"""Partie 3.4.6 -- tests for api/services/semantic_filtering.py's own
real semantic-similarity filtering/reranking. Real embeddings, no
mocking, matching this codebase's own established real-infrastructure
testing precedent."""

from api.services.semantic_filtering import (
    compute_chunk_embedding,
    compute_query_embedding,
    filter_by_similarity,
    filter_by_top_similarity,
    rerank_by_semantic_similarity,
)

_RESULTS = [
    {"chunk_id": "1", "content": "The Amazon rainforest is home to millions of species."},
    {"chunk_id": "2", "content": "Our refund policy allows returns within 30 days of purchase."},
    {"chunk_id": "3", "content": "Python is a popular programming language for data science."},
]


def test_compute_query_embedding_produces_a_real_vector():
    """Validation criterion: les embeddings sont calculés
    correctement."""
    embedding = compute_query_embedding("What is your return policy?")
    assert len(embedding) == 384
    assert all(isinstance(v, float) for v in embedding)


def test_compute_chunk_embedding_reuses_a_real_already_present_embedding():
    """Validation criterion: les embeddings sont calculés correctement
    -- an already-embedded real chunk's own vector is reused, never
    silently recomputed."""
    fake_embedding = [0.123] * 384
    chunk = {"content": "irrelevant text", "embedding": fake_embedding}
    assert compute_chunk_embedding(chunk) == fake_embedding


def test_compute_chunk_embedding_computes_fresh_when_missing():
    chunk = {"content": "The refund policy allows returns."}
    embedding = compute_chunk_embedding(chunk)
    assert len(embedding) == 384


def test_filter_by_similarity_keeps_only_real_semantically_related_results():
    """Validation criterion: le filtrage par similarité fonctionne."""
    query_embedding = compute_query_embedding("What is your return policy?")
    filtered = filter_by_similarity(_RESULTS, query_embedding, threshold=0.3)
    chunk_ids = {r["chunk_id"] for r in filtered}
    assert "2" in chunk_ids  # the real refund-policy chunk should survive
    assert len(filtered) < len(_RESULTS)  # a real, meaningful threshold discards at least one


def test_filter_by_similarity_respects_the_real_threshold_boundary():
    """Validation criterion: le seuil de similarité est respecté --
    a real, impossible threshold (1.01, above any real cosine
    similarity) discards everything."""
    query_embedding = compute_query_embedding("What is your return policy?")
    assert filter_by_similarity(_RESULTS, query_embedding, threshold=1.01) == []


def test_filter_by_top_similarity_keeps_exactly_top_k():
    """Validation criterion: le reranking sémantique fonctionne."""
    query_embedding = compute_query_embedding("return policy")
    top = filter_by_top_similarity(_RESULTS, query_embedding, top_k=2)
    assert len(top) == 2
    assert top[0]["chunk_id"] == "2"  # the real most-relevant real chunk ranks first


def test_rerank_by_semantic_similarity_reorders_without_dropping():
    query_embedding = compute_query_embedding("return policy")
    reranked = rerank_by_semantic_similarity(_RESULTS, query_embedding)
    assert len(reranked) == len(_RESULTS)
    assert {r["chunk_id"] for r in reranked} == {r["chunk_id"] for r in _RESULTS}
    assert reranked[0]["chunk_id"] == "2"


def test_filter_by_similarity_respects_the_real_kill_switch(monkeypatch):
    from api.config import settings

    monkeypatch.setattr(settings, "SEMANTIC_FILTERING_ENABLED", False)
    query_embedding = compute_query_embedding("anything")
    assert filter_by_similarity(_RESULTS, query_embedding, threshold=1.01) == _RESULTS


def test_filter_by_similarity_is_empty_input_safe():
    query_embedding = compute_query_embedding("anything")
    assert filter_by_similarity([], query_embedding) == []


def test_filter_by_top_similarity_handles_fewer_real_results_than_top_k():
    query_embedding = compute_query_embedding("anything")
    top = filter_by_top_similarity(_RESULTS, query_embedding, top_k=100)
    assert len(top) == len(_RESULTS)
