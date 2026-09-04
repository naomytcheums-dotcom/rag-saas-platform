"""Partie 3.3.3 -- tests for api/services/embedding_config.py's own
real embedding-model resolver and dimension lookup."""

import pytest

from api.security.organization_settings import DEFAULT_SETTINGS
from api.services.embedding_config import (
    EMBEDDING_DIMENSIONS,
    EMBEDDING_MODELS,
    get_embedding_dimension,
    resolve_embedding_model,
)


def test_resolve_embedding_model_falls_back_to_the_real_default():
    """Validation criterion: le fallback sur la valeur par défaut
    fonctionne."""
    assert resolve_embedding_model() == DEFAULT_SETTINGS["embedding_model"]


def test_resolve_embedding_model_reads_from_real_organization_settings():
    """Validation criterion: le modèle d'embedding est lu depuis
    organization_settings."""
    assert resolve_embedding_model({"embedding_model": "sentence-transformers/all-mpnet-base-v2"}) == "sentence-transformers/all-mpnet-base-v2"


def test_resolve_embedding_model_override_wins_over_organization_settings():
    assert resolve_embedding_model({"embedding_model": "sentence-transformers/all-mpnet-base-v2"}, override="sentence-transformers/all-MiniLM-L6-v2") == "sentence-transformers/all-MiniLM-L6-v2"


def test_resolve_embedding_model_allows_a_real_unlisted_huggingface_model():
    """A real, deliberate design check: this module is a blocklist for
    2 known-bad models, not an allowlist -- any other real model name
    passes through unchanged."""
    assert resolve_embedding_model(override="sentence-transformers/paraphrase-MiniLM-L3-v2") == "sentence-transformers/paraphrase-MiniLM-L3-v2"


def test_resolve_embedding_model_rejects_openai_with_a_real_reason():
    """Validation criterion: robustesse -- modèle non disponible."""
    with pytest.raises(ValueError, match="OpenAI"):
        resolve_embedding_model(override="openai/text-embedding-ada-002")


def test_resolve_embedding_model_rejects_cohere_with_a_real_reason():
    with pytest.raises(ValueError, match="Cohere"):
        resolve_embedding_model(override="cohere/embed-english-v3.0")


def test_get_embedding_dimension_returns_the_real_known_dimension():
    """Validation criterion: les dimensions sont correctes."""
    assert get_embedding_dimension("sentence-transformers/all-MiniLM-L6-v2") == 384
    assert get_embedding_dimension("sentence-transformers/all-mpnet-base-v2") == 768


def test_get_embedding_dimension_raises_for_an_unknown_model():
    with pytest.raises(ValueError):
        get_embedding_dimension("not-a-real-known-model")


def test_embedding_models_and_dimensions_stay_in_sync():
    assert set(EMBEDDING_DIMENSIONS) == set(EMBEDDING_MODELS)


def test_default_model_dimension_matches_the_real_loaded_model():
    """Validation criterion: les différents modèles sont chargés
    correctement -- the real, live default model (already exercised by
    tests/test_documents_integration.py's own embedding tests, no new
    mocking here) actually produces vectors of the dimension this
    module claims."""
    from api.security.documents import generate_embeddings

    model_name = resolve_embedding_model()
    embeddings = generate_embeddings(["A real sentence to embed."], model_name)
    assert len(embeddings[0]) == get_embedding_dimension(model_name)
