"""Partie 3.4.11 -- tests for api/services/duplicate_removal.py."""

from api.services.duplicate_removal import (
    deduplicate_by_content,
    deduplicate_by_hash,
    deduplicate_by_id,
    deduplicate_by_similarity,
    merge_duplicates,
)


def test_deduplicate_by_id_keeps_the_real_first_occurrence():
    """Validation criterion: le dédoublonnage par ID fonctionne."""
    chunks = [{"chunk_id": "1", "content": "a"}, {"chunk_id": "1", "content": "b"}, {"chunk_id": "2", "content": "c"}]
    deduped = deduplicate_by_id(chunks)
    assert [c["chunk_id"] for c in deduped] == ["1", "2"]
    assert deduped[0]["content"] == "a"


def test_deduplicate_by_hash_removes_real_identical_content():
    """Validation criterion: le dédoublonnage par hash fonctionne."""
    chunks = [
        {"chunk_id": "1", "content": "Real duplicate content here."},
        {"chunk_id": "2", "content": "Real duplicate content here."},
        {"chunk_id": "3", "content": "Different real content."},
    ]
    deduped = deduplicate_by_hash(chunks)
    assert len(deduped) == 2
    assert deduped[0]["chunk_id"] == "1"


def test_deduplicate_by_content_removes_real_identical_content():
    """Validation criterion: le dédoublonnage par contenu fonctionne."""
    chunks = [
        {"chunk_id": "1", "content": "Same real text."},
        {"chunk_id": "2", "content": "Same real text."},
    ]
    assert len(deduplicate_by_content(chunks)) == 1


def test_deduplicate_by_content_keeps_real_distinct_content():
    chunks = [{"chunk_id": "1", "content": "A"}, {"chunk_id": "2", "content": "B"}]
    assert len(deduplicate_by_content(chunks)) == 2


def test_deduplicate_by_similarity_removes_real_near_duplicates():
    """Validation criterion: le dédoublonnage par similarité
    fonctionne -- two real paraphrases of the same real sentence are
    recognized as near-duplicates."""
    chunks = [
        {"chunk_id": "1", "content": "The refund policy allows returns within 30 days."},
        {"chunk_id": "2", "content": "The refund policy allows returns within 30 days of purchase."},
        {"chunk_id": "3", "content": "Bananas are a good source of potassium."},
    ]
    deduped = deduplicate_by_similarity(chunks, threshold=0.9)
    assert len(deduped) < len(chunks)
    assert any(c["chunk_id"] == "3" for c in deduped)  # the real unrelated chunk always survives


def test_deduplicate_by_similarity_keeps_real_distinct_content():
    chunks = [
        {"chunk_id": "1", "content": "The refund policy allows returns within 30 days."},
        {"chunk_id": "2", "content": "Bananas are a good source of potassium."},
    ]
    assert len(deduplicate_by_similarity(chunks, threshold=0.95)) == 2


def test_merge_duplicates_keeps_the_real_highest_scoring_representative():
    """Validation criterion: la fusion de doublons fonctionne."""
    chunks = [
        {"chunk_id": "1", "content": "Same real text.", "score": 0.5},
        {"chunk_id": "2", "content": "Same real text.", "score": 0.9},
    ]
    merged = merge_duplicates(chunks, method="hash")
    assert len(merged) == 1
    assert merged[0]["chunk_id"] == "2"
    assert merged[0]["merged_from"] == ["1"]


def test_merge_duplicates_hash_method_hashes_only_the_real_content_string():
    """A regression test for a real bug found while testing:
    merge_duplicates' own "hash" method key function originally passed
    the WHOLE chunk dict to _content_hash (which expects a raw string),
    crashing on the very first real call."""
    chunks = [{"chunk_id": "1", "content": "A", "score": 0.1}, {"chunk_id": "2", "content": "B", "score": 0.2}]
    merged = merge_duplicates(chunks, method="hash")
    assert {c["chunk_id"] for c in merged} == {"1", "2"}


def test_merge_duplicates_leaves_real_unique_chunks_untouched():
    chunks = [{"chunk_id": "1", "content": "A", "score": 0.5}, {"chunk_id": "2", "content": "B", "score": 0.9}]
    merged = merge_duplicates(chunks, method="hash")
    assert len(merged) == 2
    assert "merged_from" not in merged[0]


def test_merge_duplicates_respects_the_real_kill_switch(monkeypatch):
    from api.config import settings

    monkeypatch.setattr(settings, "DEDUPLICATE_ENABLED", False)
    chunks = [{"chunk_id": "1", "content": "A", "score": 0.5}, {"chunk_id": "1", "content": "A", "score": 0.5}]
    assert merge_duplicates(chunks) == chunks


def test_merge_duplicates_rejects_an_unknown_method():
    import pytest

    with pytest.raises(ValueError):
        merge_duplicates([{"chunk_id": "1", "content": "a"}], method="not-a-real-method")


def test_deduplicate_functions_are_empty_input_safe():
    assert deduplicate_by_id([]) == []
    assert deduplicate_by_hash([]) == []
    assert deduplicate_by_content([]) == []
    assert merge_duplicates([]) == []
