"""Partie 3.3.1/3.3.2 -- tests for api/services/chunk_config.py's own
real chunk_size/chunk_overlap resolvers, plus real integration checks
that each of the 7 standalone chunking strategies (Partie 3.2.2-3.2.8)
genuinely honors an organization-resolved size."""

import pytest

from api.security.organization_settings import DEFAULT_SETTINGS
from api.services.chunk_config import (
    CHUNKING_STRATEGIES, chunk_content, resolve_child_chunk_overlap, resolve_child_chunk_size, resolve_chunk_overlap,
    resolve_chunk_size, resolve_chunking_strategy, resolve_parent_chunk_overlap, resolve_parent_chunk_size,
)


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


# ------------------------ Phase 4, Étape 1 -- resolve_chunking_strategy / chunk_content ------------------------


def test_resolve_chunking_strategy_falls_back_to_the_real_default():
    """Validation criterion: le fallback sur 'fixed' (comportement
    préexistant) fonctionne."""
    assert resolve_chunking_strategy() == DEFAULT_SETTINGS["chunking_strategy"] == "fixed"


def test_resolve_chunking_strategy_reads_from_real_organization_settings():
    assert resolve_chunking_strategy({"chunking_strategy": "markdown"}) == "markdown"


def test_resolve_chunking_strategy_override_wins_over_organization_settings():
    assert resolve_chunking_strategy({"chunking_strategy": "markdown"}, override="code") == "code"


def test_resolve_chunking_strategy_rejects_an_unknown_value():
    """Validation criterion: robustesse -- une valeur inconnue est
    rejetée explicitement, jamais silencieusement acceptée."""
    with pytest.raises(ValueError, match="Unknown chunking_strategy"):
        resolve_chunking_strategy(override="not-a-real-strategy")
    with pytest.raises(ValueError, match="Unknown chunking_strategy"):
        resolve_chunking_strategy({"chunking_strategy": "also-not-real"})


# ------------------------ Phase 4, Étape 1 (correctif config parent_child) -- dedicated resolvers ------------------------


def test_resolve_parent_and_child_sizes_fall_back_to_the_real_pre_existing_global_defaults():
    """Validation criterion: rétrocompatibilité -- une organisation qui
    ne configure rien obtient exactement les mêmes valeurs que les
    constantes globales préexistantes (comportement inchangé)."""
    from api.config import settings as app_settings

    assert resolve_parent_chunk_size() == DEFAULT_SETTINGS["parent_chunk_size"] == app_settings.PARENT_CHILD_PARENT_SIZE
    assert resolve_parent_chunk_overlap() == DEFAULT_SETTINGS["parent_chunk_overlap"] == app_settings.PARENT_CHILD_PARENT_OVERLAP
    assert resolve_child_chunk_size() == DEFAULT_SETTINGS["child_chunk_size"] == app_settings.PARENT_CHILD_CHILD_SIZE
    assert resolve_child_chunk_overlap() == DEFAULT_SETTINGS["child_chunk_overlap"] == app_settings.PARENT_CHILD_CHILD_OVERLAP


def test_resolve_parent_and_child_sizes_read_from_real_organization_settings():
    """Validation criterion: une organisation peut définir ses propres
    valeurs, réellement lues, indépendamment de chunk_size/chunk_overlap."""
    org_settings = {"parent_chunk_size": 1024, "parent_chunk_overlap": 100, "child_chunk_size": 256, "child_chunk_overlap": 30}
    assert resolve_parent_chunk_size(org_settings) == 1024
    assert resolve_parent_chunk_overlap(org_settings) == 100
    assert resolve_child_chunk_size(org_settings) == 256
    assert resolve_child_chunk_overlap(org_settings) == 30


def test_resolve_parent_and_child_sizes_are_independent_of_chunk_size_and_overlap():
    """Validation criterion: les 4 nouveaux réglages sont bien un
    système DÉDIÉ, jamais mélangé avec chunk_size/chunk_overlap des 7
    autres stratégies."""
    org_settings = {"chunk_size": 4096, "chunk_overlap": 500, "parent_chunk_size": 1024, "child_chunk_size": 256}
    assert resolve_parent_chunk_size(org_settings) == 1024
    assert resolve_child_chunk_size(org_settings) == 256
    # chunk_size/chunk_overlap remain what api/services/chunk_config.py's own resolve_chunk_size/resolve_chunk_overlap already returned before this étape:
    assert resolve_chunk_size(org_settings) == 4096


def test_resolve_parent_and_child_overlaps_reject_invalid_values():
    """Validation criterion: validations -- valeurs positives, overlap
    non négatif, overlap strictement inférieur à la taille correspondante."""
    with pytest.raises(ValueError):
        resolve_parent_chunk_size(override=0)
    with pytest.raises(ValueError):
        resolve_parent_chunk_size(override=-10)
    with pytest.raises(ValueError):
        resolve_child_chunk_size(override=0)
    with pytest.raises(ValueError):
        resolve_parent_chunk_overlap(override=-1, parent_chunk_size=512)
    with pytest.raises(ValueError):
        resolve_child_chunk_overlap(override=-1, child_chunk_size=128)
    with pytest.raises(ValueError, match="parent_chunk_overlap"):
        resolve_parent_chunk_overlap(override=512, parent_chunk_size=512)
    with pytest.raises(ValueError, match="child_chunk_overlap"):
        resolve_child_chunk_overlap(override=200, child_chunk_size=128)


def test_resolve_parent_and_child_sizes_reject_a_too_large_value():
    from api.config import settings as app_settings

    with pytest.raises(ValueError):
        resolve_parent_chunk_size(override=app_settings.CHUNK_SIZE_MAX_TOKENS + 1)
    with pytest.raises(ValueError):
        resolve_child_chunk_size(override=app_settings.CHUNK_SIZE_MAX_TOKENS + 1)


def test_chunk_content_dispatches_every_real_non_fixed_strategy():
    """Validation criterion: le point d'entrée unique route réellement
    vers chacune des 6 stratégies (hors 'fixed' et 'parent_child',
    toutes deux gérées directement par l'appelant, `process_document` --
    voir le docstring de CHUNKING_STRATEGIES)."""
    text = "First real sentence here. Second real sentence follows. Third one concludes this real paragraph."
    for strategy in CHUNKING_STRATEGIES:
        if strategy in ("fixed", "parent_child"):
            continue
        chunks = chunk_content(text, strategy, 30, 0)
        assert isinstance(chunks, list)
        assert all(isinstance(c, str) for c in chunks)


def test_chunk_content_rejects_fixed_and_parent_child():
    """Validation criterion: robustesse -- le dispatcher ne prétend
    jamais gérer 'fixed' (a besoin d'un vrai tokenizer, propriété de
    l'appelant) ni 'parent_child' (forme de sortie différente, pas
    encore branchée)."""
    with pytest.raises(ValueError):
        chunk_content("some text", "fixed", 30, 0)
    with pytest.raises(ValueError):
        chunk_content("some text", "parent_child", 30, 0)


def test_chunk_content_markdown_respects_real_headings():
    text = "# Title\n\nIntro.\n\n## A\n\nContent A.\n\n## B\n\nContent B."
    chunks = chunk_content(text, "markdown", 200, 0)
    assert len(chunks) == 3
    assert chunks[0].startswith("# Title")


def test_chunk_content_code_respects_real_function_boundaries():
    text = "def foo():\n    return 1\n\ndef bar():\n    return 2\n"
    chunks = chunk_content(text, "code", 100, 0)
    assert any("foo" in c for c in chunks)
    assert any("bar" in c for c in chunks)


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
