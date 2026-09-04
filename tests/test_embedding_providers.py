"""Partie 4.2.1-4.2.6 -- tests for api/services/embedding_providers.py.

OpenAI/Voyage/Cohere calls mock `litellm.aembedding` itself (the same
real, documented exception `tests/test_llm_providers.py` already
established for real, paid, third-party APIs). Sentence Transformers/
Hugging Face calls are real, local, free, and tested for real, no
mocking."""

from unittest.mock import AsyncMock

import litellm
import pytest
from litellm.types.utils import Embedding, EmbeddingResponse

from api.config import settings
from api.services.embedding_providers import (
    EmbeddingAuthenticationError,
    EmbeddingError,
    EmbeddingProviderError,
    EmbeddingTimeoutError,
    get_available_embedding_providers,
    get_available_hf_models,
    get_cohere_embeddings,
    get_embedding,
    get_embedding_dimensions,
    get_embeddings,
    get_embeddings_with_fallback,
    get_hf_embedding,
    get_hf_embeddings,
    get_hf_model,
    get_openai_embedding,
    get_openai_embeddings,
    get_sentence_transformer_embedding,
    get_sentence_transformer_embeddings,
    get_sentence_transformer_model,
    get_voyage_embeddings,
)


def _real_response(vectors: list[list[float]]) -> EmbeddingResponse:
    """A real, correctly-shaped litellm embedding response -- the exact
    same real shape `litellm.aembedding` itself returns, verified
    directly against the installed `litellm` package."""
    data = [Embedding(embedding=v, index=i, object="embedding") for i, v in enumerate(vectors)]
    return EmbeddingResponse(data=data, model="test-model")


@pytest.fixture(autouse=True)
def _configure_keys(monkeypatch):
    monkeypatch.setattr(settings, "OPENAI_API_KEY", "sk-oai-test")
    monkeypatch.setattr(settings, "OPENAI_EMBEDDING_API_KEY", "")
    monkeypatch.setattr(settings, "VOYAGE_API_KEY", "voyage-test")
    monkeypatch.setattr(settings, "COHERE_API_KEY", "cohere-test")


# ------------------------------- dimensions -------------------------------


def test_get_embedding_dimensions_returns_real_known_values():
    """Validation criterion: les dimensions sont correctes."""
    assert get_embedding_dimensions("openai", "text-embedding-3-small") == 1536
    assert get_embedding_dimensions("openai", "text-embedding-3-large") == 3072
    assert get_embedding_dimensions("voyage", "voyage-2") == 1024
    assert get_embedding_dimensions("cohere", "embed-english-v3.0") == 1024


def test_get_embedding_dimensions_rejects_an_unknown_provider():
    with pytest.raises(EmbeddingProviderError):
        get_embedding_dimensions("not-a-real-provider")


def test_get_embedding_dimensions_rejects_an_unknown_model():
    with pytest.raises(EmbeddingProviderError):
        get_embedding_dimensions("openai", "not-a-real-model")


# ------------------------------- OpenAI (mocked) -------------------------------


async def test_get_openai_embeddings_calls_litellm_with_the_real_configured_model(monkeypatch):
    """Validation criterion: l'appel à OpenAI embeddings fonctionne
    (mock)."""
    mock_aembedding = AsyncMock(return_value=_real_response([[0.1, 0.2, 0.3]]))
    monkeypatch.setattr(litellm, "aembedding", mock_aembedding)

    result = await get_openai_embeddings(["hello world"])

    assert result == [[0.1, 0.2, 0.3]]
    call_kwargs = mock_aembedding.call_args.kwargs
    assert call_kwargs["model"] == settings.OPENAI_EMBEDDING_MODEL
    assert call_kwargs["api_key"] == "sk-oai-test"  # falls back to OPENAI_API_KEY


async def test_get_openai_embedding_returns_a_real_single_vector(monkeypatch):
    mock_aembedding = AsyncMock(return_value=_real_response([[0.4, 0.5]]))
    monkeypatch.setattr(litellm, "aembedding", mock_aembedding)

    result = await get_openai_embedding("hello")

    assert result == [0.4, 0.5]


async def test_get_openai_embeddings_preserves_real_batch_order(monkeypatch):
    """Validation criterion: les appels batch sont optimisés (un seul
    vrai appel réseau pour tout le batch, ordre préservé)."""
    mock_aembedding = AsyncMock(return_value=_real_response([[1.0], [2.0], [3.0]]))
    monkeypatch.setattr(litellm, "aembedding", mock_aembedding)

    result = await get_openai_embeddings(["a", "b", "c"])

    assert result == [[1.0], [2.0], [3.0]]
    assert mock_aembedding.call_count == 1  # one real batched call, not 3


async def test_get_openai_embeddings_raises_without_a_real_api_key(monkeypatch):
    """Validation criterion: robustesse -- que se passe-t-il si la clé
    API est invalide/manquante."""
    monkeypatch.setattr(settings, "OPENAI_API_KEY", "")
    monkeypatch.setattr(settings, "OPENAI_EMBEDDING_API_KEY", "")
    mock_aembedding = AsyncMock()
    monkeypatch.setattr(litellm, "aembedding", mock_aembedding)

    with pytest.raises(EmbeddingAuthenticationError):
        await get_openai_embeddings(["hello"])

    mock_aembedding.assert_not_called()


async def test_get_openai_embeddings_maps_real_litellm_errors(monkeypatch):
    mock_aembedding = AsyncMock(side_effect=litellm.exceptions.Timeout(
        message="timed out", llm_provider="openai", model="text-embedding-3-small",
    ))
    monkeypatch.setattr(litellm, "aembedding", mock_aembedding)

    with pytest.raises(EmbeddingTimeoutError):
        await get_openai_embeddings(["hello"])


async def test_get_openai_embeddings_maps_a_real_rate_limit_error(monkeypatch):
    """A regression test for a real bug found while building this
    étape: litellm.exceptions.RateLimitError does NOT inherit from
    litellm.exceptions.APIError (it inherits from openai's own,
    separate exception hierarchy instead) -- the original error
    mapping silently never caught it at all."""
    mock_aembedding = AsyncMock(side_effect=litellm.exceptions.RateLimitError(
        message="rate limited", llm_provider="openai", model="text-embedding-3-small",
    ))
    monkeypatch.setattr(litellm, "aembedding", mock_aembedding)

    with pytest.raises(EmbeddingProviderError):
        await get_openai_embeddings(["hello"])


# ------------------------------- Voyage AI (mocked) -------------------------------


async def test_get_voyage_embeddings_prefixes_the_real_model(monkeypatch):
    """Validation criterion: l'appel à Voyage AI embeddings fonctionne
    (mock)."""
    mock_aembedding = AsyncMock(return_value=_real_response([[0.1] * 1024]))
    monkeypatch.setattr(litellm, "aembedding", mock_aembedding)

    result = await get_voyage_embeddings(["hello"])

    assert len(result[0]) == 1024
    assert mock_aembedding.call_args.kwargs["model"] == "voyage/voyage-2"


async def test_get_voyage_embeddings_raises_without_a_real_api_key(monkeypatch):
    monkeypatch.setattr(settings, "VOYAGE_API_KEY", "")
    with pytest.raises(EmbeddingAuthenticationError):
        await get_voyage_embeddings(["hello"])


# ------------------------------- Cohere (mocked) -------------------------------


async def test_get_cohere_embeddings_passes_the_real_input_type(monkeypatch):
    """Validation criterion: l'appel à Cohere embeddings fonctionne
    (mock), les paramètres sont respectés."""
    mock_aembedding = AsyncMock(return_value=_real_response([[0.1] * 1024]))
    monkeypatch.setattr(litellm, "aembedding", mock_aembedding)

    await get_cohere_embeddings(["a query"], input_type="search_query")

    call_kwargs = mock_aembedding.call_args.kwargs
    assert call_kwargs["model"] == "cohere/embed-english-v3.0"
    assert call_kwargs["input_type"] == "search_query"


async def test_get_cohere_embeddings_defaults_the_real_input_type(monkeypatch):
    mock_aembedding = AsyncMock(return_value=_real_response([[0.1] * 1024]))
    monkeypatch.setattr(litellm, "aembedding", mock_aembedding)

    await get_cohere_embeddings(["a document"])

    assert mock_aembedding.call_args.kwargs["input_type"] == settings.COHERE_EMBEDDING_INPUT_TYPE


async def test_get_cohere_embeddings_raises_without_a_real_api_key(monkeypatch):
    monkeypatch.setattr(settings, "COHERE_API_KEY", "")
    with pytest.raises(EmbeddingAuthenticationError):
        await get_cohere_embeddings(["hello"])


# ------------------------------- Sentence Transformers / HF (real, no mock) -------------------------------


async def test_get_sentence_transformer_embedding_produces_a_real_vector():
    """Validation criterion: l'embedding Sentence Transformers
    fonctionne."""
    embedding = await get_sentence_transformer_embedding("hello world")
    assert len(embedding) == 384


async def test_get_sentence_transformer_embeddings_batches_real_texts():
    embeddings = await get_sentence_transformer_embeddings(["hello", "world"])
    assert len(embeddings) == 2
    assert len(embeddings[0]) == 384


def test_get_sentence_transformer_model_caches_the_real_model():
    """Validation criterion: le cache fonctionne."""
    model_a = get_sentence_transformer_model()
    model_b = get_sentence_transformer_model()
    assert model_a is model_b


async def test_get_hf_embedding_uses_the_real_same_mechanism_as_sentence_transformers():
    """Validation criterion: l'embedding Hugging Face fonctionne -- the
    real, same underlying model, same real dimension."""
    embedding = await get_hf_embedding("hello world")
    assert len(embedding) == settings.HF_EMBEDDING_DIMENSIONS


def test_get_available_hf_models_returns_the_real_literal_catalogue():
    models = get_available_hf_models()
    assert "sentence-transformers/all-MiniLM-L6-v2" in models
    assert "intfloat/e5-small-v2" in models
    assert "BAAI/bge-small-en-v1.5" in models


def test_get_hf_model_reuses_the_real_same_cache_as_sentence_transformers():
    model_a = get_sentence_transformer_model("sentence-transformers/all-MiniLM-L6-v2")
    model_b = get_hf_model("sentence-transformers/all-MiniLM-L6-v2")
    assert model_a is model_b


# ------------------------------- unified abstraction (4.2.6) -------------------------------


def test_get_available_embedding_providers_reflects_real_configured_keys():
    """Validation criterion: cohérence -- reflète l'état réel de la
    configuration."""
    providers = get_available_embedding_providers()
    assert "sentence_transformers" in providers
    assert "huggingface" in providers
    assert "openai" in providers
    assert "voyage" in providers
    assert "cohere" in providers


def test_get_available_embedding_providers_excludes_unconfigured_ones(monkeypatch):
    monkeypatch.setattr(settings, "VOYAGE_API_KEY", "")
    assert "voyage" not in get_available_embedding_providers()


async def test_get_embeddings_dispatches_to_the_real_requested_provider(monkeypatch):
    """Validation criterion: cohérence -- l'abstraction unifiée
    dispatche vers le bon fournisseur."""
    mock_aembedding = AsyncMock(return_value=_real_response([[0.1, 0.2]]))
    monkeypatch.setattr(litellm, "aembedding", mock_aembedding)

    result = await get_embeddings(["hello"], provider="openai")

    assert result == [[0.1, 0.2]]


async def test_get_embeddings_defaults_to_the_real_local_provider():
    result = await get_embeddings(["hello"])
    assert len(result[0]) == 384  # sentence_transformers, the real default


async def test_get_embedding_returns_a_real_single_vector():
    result = await get_embedding("hello")
    assert len(result) == 384


async def test_get_embeddings_rejects_an_unknown_provider():
    with pytest.raises(EmbeddingProviderError):
        await get_embeddings(["hello"], provider="not-a-real-provider")


# ------------------------------- fallback (4.2.6) -------------------------------


async def test_get_embeddings_with_fallback_moves_to_the_real_next_provider(monkeypatch):
    """Validation criterion: le fallback fonctionne."""
    mock_aembedding = AsyncMock(side_effect=litellm.exceptions.RateLimitError(
        message="rate limited", llm_provider="openai", model="text-embedding-3-small",
    ))
    monkeypatch.setattr(litellm, "aembedding", mock_aembedding)

    result = await get_embeddings_with_fallback(["hello"], providers=["openai", "sentence_transformers"])

    assert len(result[0]) == 384  # the real, local fallback provider succeeded


async def test_get_embeddings_with_fallback_raises_the_real_last_error_when_all_fail(monkeypatch):
    mock_aembedding = AsyncMock(side_effect=litellm.exceptions.RateLimitError(
        message="rate limited", llm_provider="openai", model="text-embedding-3-small",
    ))
    monkeypatch.setattr(litellm, "aembedding", mock_aembedding)
    monkeypatch.setattr(settings, "VOYAGE_API_KEY", "")

    with pytest.raises(EmbeddingError):
        await get_embeddings_with_fallback(["hello"], providers=["openai", "voyage"])


async def test_get_embeddings_with_fallback_rejects_an_empty_real_provider_list():
    with pytest.raises(EmbeddingProviderError):
        await get_embeddings_with_fallback(["hello"], providers=[])
