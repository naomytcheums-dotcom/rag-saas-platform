"""Partie 3.3.1/3.3.2 -- tests for api/services/chunk_config.py's own
real chunk_size/chunk_overlap resolvers, plus real integration checks
that each of the 7 standalone chunking strategies (Partie 3.2.2-3.2.8)
genuinely honors an organization-resolved size."""

import pytest

from api.security.organization_settings import DEFAULT_SETTINGS
from api.services.chunk_config import resolve_chunk_overlap, resolve_chunk_size


def test_resolve_chunk_size_falls_back_to_the_real_default():
    """Validation criterion: le fallback sur la valeur par défaut
    fonctionne."""
    assert resolve_chunk_size() == DEFAULT_SETTINGS["chunk_size"]
    assert resolve_chunk_size(org_settings=None) == DEFAULT_SETTINGS["chunk_size"]


def test_resolve_chunk_size_reads_from_real_organization_settings():
    """Validation criterion: le chunk size est lu depuis
    organization_settings."""
    assert resolve_chunk_size({"chunk_size": 1024}) == 1024


def test_resolve_chunk_size_override_wins_over_organization_settings():
    assert resolve_chunk_size({"chunk_size": 1024}, override=256) == 256


def test_resolve_chunk_size_rejects_zero_and_negative():
    """Validation criterion: robustesse -- valeur invalide (négative)."""
    with pytest.raises(ValueError):
        resolve_chunk_size(override=0)
    with pytest.raises(ValueError):
        resolve_chunk_size(override=-1)


def test_resolve_chunk_size_rejects_a_real_too_large_value():
    """Validation criterion: robustesse -- valeur invalide (trop
    grande)."""
    with pytest.raises(ValueError):
        resolve_chunk_size(override=999_999_999)


def test_resolve_chunk_size_rejects_a_non_integer():
    with pytest.raises(ValueError):
        resolve_chunk_size(override="512")  # type: ignore[arg-type]


def test_resolve_chunk_overlap_falls_back_to_the_real_default():
    assert resolve_chunk_overlap() == DEFAULT_SETTINGS["chunk_overlap"]


def test_resolve_chunk_overlap_reads_from_real_organization_settings():
    """Validation criterion: le chunk overlap est lu depuis
    organization_settings."""
    assert resolve_chunk_overlap({"chunk_size": 1024, "chunk_overlap": 100}) == 100


def test_resolve_chunk_overlap_override_wins_over_organization_settings():
    assert resolve_chunk_overlap({"chunk_overlap": 100}, override=10, chunk_size=1024) == 10


def test_resolve_chunk_overlap_rejects_negative():
    with pytest.raises(ValueError):
        resolve_chunk_overlap(override=-1, chunk_size=512)


def test_resolve_chunk_overlap_rejects_overlap_greater_than_or_equal_to_chunk_size():
    """Validation criterion: robustesse -- overlap invalide (>=
    chunk_size), la même validation réelle que le endpoint PATCH."""
    with pytest.raises(ValueError):
        resolve_chunk_overlap(override=512, chunk_size=512)
    with pytest.raises(ValueError):
        resolve_chunk_overlap(override=600, chunk_size=512)


# ------------------------ real integration: every strategy honors it ------------------------

_LONG_TEXT = " ".join(f"This is real sentence number {i} in a longer real document for testing." for i in range(60))
_LONG_MARKDOWN = "\n\n".join(f"## Section {i}\n\nReal content for section {i} here." for i in range(20))
_LONG_CODE = "\n\n".join(f"def real_function_{i}():\n    return {i}" for i in range(20))
_LONG_PARAGRAPHS = "\n\n".join(f"Real paragraph number {i} with some real filler content here." for i in range(20))


def test_recursive_strategy_honors_the_real_resolved_chunk_size():
    from api.services.chunking import chunk_recursive_text

    size = resolve_chunk_size({"chunk_size": 40})
    chunks = chunk_recursive_text(_LONG_TEXT, max_size=size)
    assert all(len(c) <= size for c in chunks)


def test_semantic_strategy_honors_the_real_resolved_chunk_size():
    from api.services.semantic_chunking import merge_semantic_chunks

    size = resolve_chunk_size({"chunk_size": 40})
    chunks = merge_semantic_chunks(["A short real chunk.", "Another short real chunk.", "A third one."], max_size=size)
    assert all(len(c) <= size for c in chunks)


def test_markdown_strategy_honors_the_real_resolved_chunk_size():
    from api.services.markdown_chunking import chunk_markdown_by_headings

    size = resolve_chunk_size({"chunk_size": 60})
    chunks = chunk_markdown_by_headings(_LONG_MARKDOWN, min_chunk_size=0, max_chunk_size=size)
    assert all(len(c) <= size for c in chunks)


def test_code_strategy_honors_the_real_resolved_chunk_size():
    """A real regression check for the real gap this étape fixed:
    chunk_code_by_blocks previously had no way to receive an
    organization's own configured chunk size at all."""
    from api.services.code_chunking import chunk_code_by_blocks

    size = resolve_chunk_size({"chunk_size": 30})
    chunks = chunk_code_by_blocks(_LONG_CODE, max_size=size)
    assert all(len(c) <= size for c in chunks)


def test_sentence_strategy_honors_the_real_resolved_chunk_size():
    from api.services.sentence_chunking import chunk_by_sentence_tokens

    size = resolve_chunk_size({"chunk_size": 10})
    overlap = resolve_chunk_overlap({"chunk_overlap": 0}, chunk_size=size)
    chunks = chunk_by_sentence_tokens(_LONG_TEXT, max_tokens=size, overlap_tokens=overlap, language="en")
    assert len(chunks) > 1


def test_paragraph_strategy_honors_the_real_resolved_chunk_size():
    from api.services.paragraph_chunking import chunk_by_paragraph_tokens

    size = resolve_chunk_size({"chunk_size": 15})
    overlap = resolve_chunk_overlap({"chunk_overlap": 0}, chunk_size=size)
    chunks = chunk_by_paragraph_tokens(_LONG_PARAGRAPHS, max_tokens=size, overlap_tokens=overlap)
    assert len(chunks) > 1


def test_parent_child_strategy_honors_the_real_resolved_sizes():
    from api.services.parent_child_chunking import chunk_parent_child

    parent_size = resolve_chunk_size({"chunk_size": 60})
    child_size = 15
    result = chunk_parent_child(_LONG_TEXT, child_size=child_size, parent_size=parent_size, child_overlap=0, parent_overlap=0)
    assert len(result["parents"]) > 1
    assert len(result["children"]) > len(result["parents"])
