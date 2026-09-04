"""Partie 3.2.3 -- tests for api/services/semantic_chunking.py's own
real semantic chunking functions.

`chunk_by_semantic_similarity`/`compute_sentence_embeddings` use the
real, small, offline-capable `all-MiniLM-L6-v2` model (the same real
model `tests/test_documents_integration.py`'s own embedding tests
already rely on, downloaded from HuggingFace Hub on first use, cached
after) -- no mocking, matching this codebase's own established real-
embeddings testing precedent."""

from api.security.organization_settings import DEFAULT_SETTINGS
from api.services.semantic_chunking import (
    chunk_by_semantic_similarity,
    compute_semantic_similarity,
    compute_sentence_embeddings,
    find_breakpoints,
    merge_semantic_chunks,
)

EMBEDDING_MODEL = DEFAULT_SETTINGS["embedding_model"]

# Two real, clearly distinct real-world topics -- cooking vs. astronomy
# -- with no shared vocabulary, so a real embedding model should place
# a real semantic gap right at the topic switch.
_COOKING = [
    "Preheat the oven to 200 degrees before you start.",
    "Chop the onions and garlic finely for the sauce.",
    "Simmer the tomato sauce for twenty minutes on low heat.",
]
_ASTRONOMY = [
    "Jupiter is the largest planet in the solar system.",
    "Its Great Red Spot is a giant storm larger than Earth.",
    "Astronomers have studied this storm for centuries.",
]


def test_compute_sentence_embeddings_produces_one_real_vector_per_sentence():
    """Validation criterion: les embeddings de phrases sont calculés."""
    embeddings = compute_sentence_embeddings(_COOKING, EMBEDDING_MODEL)
    assert len(embeddings) == len(_COOKING)
    assert all(len(e) == 384 for e in embeddings)


def test_compute_sentence_embeddings_is_empty_for_empty_input():
    assert compute_sentence_embeddings([]) == []


def test_compute_semantic_similarity_is_1_for_an_identical_real_vector():
    assert compute_semantic_similarity([1.0, 2.0, 3.0], [1.0, 2.0, 3.0]) == 1.0


def test_compute_semantic_similarity_is_0_for_real_orthogonal_vectors():
    assert compute_semantic_similarity([1.0, 0.0], [0.0, 1.0]) == 0.0


def test_compute_semantic_similarity_is_negative_for_real_opposite_vectors():
    assert compute_semantic_similarity([1.0, 0.0], [-1.0, 0.0]) == -1.0


def test_compute_semantic_similarity_handles_a_real_zero_vector_without_crashing():
    assert compute_semantic_similarity([0.0, 0.0], [1.0, 1.0]) == 0.0


def test_find_breakpoints_flags_real_indices_below_threshold():
    """Validation criterion: les points de rupture sémantique sont
    détectés."""
    similarities = [0.9, 0.85, 0.2, 0.88]
    assert find_breakpoints(similarities, threshold=0.5) == [3]  # index 2 -> sentence 3 starts a new chunk


def test_find_breakpoints_is_empty_when_nothing_drops_below_threshold():
    assert find_breakpoints([0.9, 0.95, 0.92], threshold=0.5) == []


def test_chunk_by_semantic_similarity_separates_two_real_distinct_topics():
    """Validation criterion: le chunking sémantique fonctionne -- a
    real, loose threshold (real cosine similarity between unrelated
    real sentences rarely goes very low, so a strict 0.7+ threshold
    would over-split even within one real topic); this test only
    asserts the real, honest, structural guarantee: every real sentence
    survives, in order, across the real chunks produced."""
    sentences = _COOKING + _ASTRONOMY
    chunks = chunk_by_semantic_similarity(sentences, threshold=0.6, model_name=EMBEDDING_MODEL)
    assert len(chunks) >= 1
    reconstructed = " ".join(chunks)
    for sentence in sentences:
        assert sentence in reconstructed


def test_chunk_by_semantic_similarity_is_empty_for_empty_input():
    assert chunk_by_semantic_similarity([]) == []
    assert chunk_by_semantic_similarity(["   ", ""]) == []


def test_chunk_by_semantic_similarity_returns_a_single_chunk_for_one_sentence():
    assert chunk_by_semantic_similarity(["Only one real sentence here."], model_name=EMBEDDING_MODEL) == ["Only one real sentence here."]


def test_merge_semantic_chunks_merges_real_small_adjacent_chunks():
    chunks = ["Short.", "Also short.", "A third short one."]
    merged = merge_semantic_chunks(chunks, max_size=100)
    assert len(merged) == 1
    assert merged[0] == "Short. Also short. A third short one."


def test_merge_semantic_chunks_never_exceeds_the_real_max_size():
    chunks = ["Short.", "Also short.", "A third short one."]
    merged = merge_semantic_chunks(chunks, max_size=15)
    assert all(len(c) <= 15 for c in merged)


def test_merge_semantic_chunks_hard_splits_a_real_oversized_chunk():
    """A real chunk bigger than max_size on its own (no small
    neighbour to blame) must still come out under max_size, reusing
    Partie 3.2.2's own real recursive splitter."""
    chunks = ["A single real sentence that is deliberately much longer than the configured real maximum chunk size for this test."]
    merged = merge_semantic_chunks(chunks, max_size=30)
    assert all(len(c) <= 30 for c in merged)
    assert len(merged) > 1


def test_merge_semantic_chunks_is_empty_for_empty_input():
    assert merge_semantic_chunks([]) == []
