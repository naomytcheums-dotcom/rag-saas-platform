"""Partie 3.4.12/3.4.16 -- tests for api/services/mmr.py's own real
Maximal Marginal Relevance diversification. Real embeddings, no
mocking, matching this codebase's own established real-infrastructure
testing precedent."""

import pytest

from api.services.mmr import compute_diversity_penalty, compute_mmr, rerank_by_mmr, select_diverse_chunks
from api.services.semantic_filtering import compute_query_embedding

_CHUNKS = [
    {"chunk_id": "1", "content": "The refund policy allows returns within 30 days."},
    {"chunk_id": "2", "content": "Refunds are accepted for up to thirty days after purchase."},
    {"chunk_id": "3", "content": "Bananas are a good source of potassium and fiber."},
    {"chunk_id": "4", "content": "Our office relocated to a new building downtown."},
]


def test_compute_diversity_penalty_is_zero_with_nothing_selected():
    """Validation criterion: la pénalité de diversité est calculée
    correctement."""
    assert compute_diversity_penalty([1.0, 0.0], []) == 0.0


def test_compute_diversity_penalty_is_the_real_max_similarity():
    penalty = compute_diversity_penalty([1.0, 0.0], [[1.0, 0.0], [0.0, 1.0]])
    assert penalty == 1.0  # identical to the first real selected embedding


def test_compute_mmr_rejects_an_invalid_lambda():
    """Validation criterion: robustesse -- paramètre lambda invalide."""
    with pytest.raises(ValueError):
        compute_mmr([1.0, 0.0], [[1.0, 0.0]], lambda_param=1.5)
    with pytest.raises(ValueError):
        compute_mmr([1.0, 0.0], [[1.0, 0.0]], lambda_param=-0.1)


def test_compute_mmr_accepts_the_real_boundary_lambda_values():
    compute_mmr([1.0, 0.0], [[1.0, 0.0], [0.0, 1.0]], lambda_param=0.0, top_k=1)
    compute_mmr([1.0, 0.0], [[1.0, 0.0], [0.0, 1.0]], lambda_param=1.0, top_k=1)


def test_select_diverse_chunks_diversifies_real_results():
    """Validation criterion: la sélection diversifiée fonctionne --
    a real, low lambda (diversity-favoring) should not select both
    real near-duplicate refund-policy chunks."""
    query_embedding = compute_query_embedding("refund policy")
    selected = select_diverse_chunks(_CHUNKS, query_embedding, lambda_param=0.3, top_k=2)
    assert len(selected) == 2
    selected_ids = {c["chunk_id"] for c in selected}
    assert not {"1", "2"}.issubset(selected_ids)  # never both real near-duplicates together


def test_select_diverse_chunks_with_lambda_1_behaves_like_pure_relevance():
    """Validation criterion: le paramètre lambda est respecté -- with
    real lambda=1 (pure relevance, item 3's own literal meaning), the
    real top result is always the single most relevant real chunk."""
    query_embedding = compute_query_embedding("refund policy")
    selected = select_diverse_chunks(_CHUNKS, query_embedding, lambda_param=1.0, top_k=1)
    assert len(selected) == 1
    assert selected[0]["chunk_id"] in {"1", "2"}


def test_select_diverse_chunks_respects_the_real_top_k():
    query_embedding = compute_query_embedding("anything")
    selected = select_diverse_chunks(_CHUNKS, query_embedding, top_k=3)
    assert len(selected) == 3


def test_rerank_by_mmr_is_a_real_alias_for_select_diverse_chunks():
    query_embedding = compute_query_embedding("refund policy")
    a = select_diverse_chunks(_CHUNKS, query_embedding, lambda_param=0.5, top_k=2)
    b = rerank_by_mmr(_CHUNKS, query_embedding, lambda_param=0.5, top_k=2)
    assert [c["chunk_id"] for c in a] == [c["chunk_id"] for c in b]


def test_select_diverse_chunks_respects_the_real_kill_switch(monkeypatch):
    from api.config import settings

    monkeypatch.setattr(settings, "MMR_ENABLED", False)
    query_embedding = compute_query_embedding("anything")
    assert select_diverse_chunks(_CHUNKS, query_embedding, top_k=1) == _CHUNKS


def test_select_diverse_chunks_is_empty_input_safe():
    query_embedding = compute_query_embedding("anything")
    assert select_diverse_chunks([], query_embedding) == []
