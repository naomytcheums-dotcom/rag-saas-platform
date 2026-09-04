"""Partie 3.2.8 -- tests for api/services/parent_child_chunking.py's
own real, hierarchical chunking functions."""

from api.services.parent_child_chunking import (
    chunk_parent_child,
    create_child_chunks,
    create_parent_chunks,
    get_parent_context,
    link_child_to_parent,
)

_TEXT = " ".join(f"This is real sentence number {i} in a longer real document." for i in range(40))


def test_create_parent_chunks_produces_real_located_parents():
    """Validation criterion: la création de chunks parents
    fonctionne."""
    parents = create_parent_chunks(_TEXT, parent_size=30, parent_overlap=5)
    assert len(parents) > 1
    for parent in parents:
        assert parent["text"] == _TEXT[parent["start"]:parent["end"]]
        assert parent["id"].startswith("parent-")


def test_create_parent_chunks_is_empty_for_empty_input():
    assert create_parent_chunks("") == []


def test_create_child_chunks_produces_real_children_inside_their_own_parent():
    """Validation criterion: la création de chunks enfants
    fonctionne -- every real child's own span falls strictly inside its
    own real parent's span."""
    parents = create_parent_chunks(_TEXT, parent_size=60, parent_overlap=0)
    children = create_child_chunks(_TEXT, parents, child_size=15, child_overlap=0)
    assert len(children) > len(parents)
    for child in children:
        parent = next(p for p in parents if p["id"] == child["parent_id"])
        assert parent["start"] <= child["start"] and child["end"] <= parent["end"]
        assert child["text"] in parent["text"]


def test_create_child_chunks_is_empty_when_there_are_no_real_parents():
    assert create_child_chunks(_TEXT, []) == []


def test_link_child_to_parent_attaches_real_parent_fields():
    """Validation criterion: la liaison parent-enfant fonctionne."""
    parent = {"id": "parent-0", "text": "Real parent text.", "start": 0, "end": 18}
    child = {"id": "child-0", "text": "Real parent", "start": 0, "end": 11}
    linked = link_child_to_parent(child, parent)
    assert linked["parent_id"] == "parent-0"
    assert linked["parent_text"] == "Real parent text."


def test_get_parent_context_returns_real_linked_parent_text():
    """Validation criterion: le contexte parent est récupéré."""
    parents = create_parent_chunks(_TEXT, parent_size=60, parent_overlap=0)
    children = create_child_chunks(_TEXT, parents, child_size=15, child_overlap=0)
    context = get_parent_context(children[0])
    assert context == children[0]["parent_text"]
    assert children[0]["text"] in context


def test_get_parent_context_is_none_for_an_unlinked_child():
    assert get_parent_context({"id": "child-0", "text": "x"}) is None


def test_chunk_parent_child_produces_a_real_full_hierarchy():
    """Validation criterion: le pipeline complet fonctionne (petits et
    gros documents)."""
    result = chunk_parent_child(_TEXT, child_size=15, parent_size=60, child_overlap=0, parent_overlap=0)
    assert len(result["parents"]) > 0
    assert len(result["children"]) > len(result["parents"])
    assert all(c["parent_id"] for c in result["children"])


def test_chunk_parent_child_handles_a_real_small_document():
    result = chunk_parent_child("Just one short real sentence.", child_size=100, parent_size=100)
    assert len(result["parents"]) == 1
    assert len(result["children"]) >= 1


def test_chunk_parent_child_respects_the_real_kill_switch(monkeypatch):
    from api.config import settings

    monkeypatch.setattr(settings, "PARENT_CHILD_ENABLED", False)
    assert chunk_parent_child(_TEXT) == {"parents": [], "children": []}


def test_chunk_parent_child_supports_the_real_recursive_strategy():
    result = chunk_parent_child(_TEXT, child_size=100, parent_size=400, strategy="recursive")
    assert len(result["parents"]) >= 1
    assert len(result["children"]) >= 1


def test_chunk_parent_child_supports_the_real_paragraph_strategy():
    text = "\n\n".join(f"Real paragraph number {i} with some real filler content." for i in range(20))
    result = chunk_parent_child(text, child_size=20, parent_size=80, strategy="paragraph")
    assert len(result["parents"]) >= 1
    assert len(result["children"]) >= 1


def test_chunk_parent_child_rejects_an_unknown_real_strategy():
    import pytest

    with pytest.raises(ValueError):
        chunk_parent_child(_TEXT, strategy="not-a-real-strategy")
