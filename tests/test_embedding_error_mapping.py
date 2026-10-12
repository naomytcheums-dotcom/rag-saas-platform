"""Phase 5 of the 2026-10-12 security audit: the embedding providers had the defect already fixed for the chat providers (tests/test_llm_error_mapping.py).

LiteLLM's connection, 5xx and not-found errors do not inherit from `litellm.exceptions.APIError`, so they escaped `_call_litellm_embedding` as raw LiteLLM exceptions:
`get_embeddings_with_fallback` (which only catches EmbeddingError) never moved on to the next provider when the first one was down. Offline: `litellm.aembedding` is mocked.
"""

from unittest.mock import AsyncMock

import litellm
import pytest
from litellm.types.utils import Embedding, EmbeddingResponse

from api.config import settings
from api.services.embedding_providers import EmbeddingProviderError, get_embeddings_with_fallback, get_openai_embeddings


@pytest.fixture(autouse=True)
def _configure_keys(monkeypatch):
    monkeypatch.setattr(settings, "OPENAI_API_KEY", "sk-oai-test")
    monkeypatch.setattr(settings, "OPENAI_EMBEDDING_API_KEY", "")
    monkeypatch.setattr(settings, "VOYAGE_API_KEY", "voyage-test")


def _errors():
    kwargs = {"llm_provider": "openai", "model": "m"}
    return [
        litellm.exceptions.APIConnectionError(message="refused", **kwargs),
        litellm.exceptions.InternalServerError(message="boom", **kwargs),
        litellm.exceptions.ServiceUnavailableError(message="down", **kwargs),
        litellm.exceptions.NotFoundError(message="model not found", **kwargs),
        litellm.exceptions.BadRequestError(message="bad request", **kwargs),
    ]


@pytest.mark.parametrize("error", _errors(), ids=lambda e: type(e).__name__)
async def test_litellm_connection_and_status_errors_become_embedding_provider_errors(monkeypatch, error):
    monkeypatch.setattr(litellm, "aembedding", AsyncMock(side_effect=error))
    with pytest.raises(EmbeddingProviderError):
        await get_openai_embeddings(["hello"])


async def test_the_fallback_moves_on_when_the_first_provider_is_down(monkeypatch):
    answer = EmbeddingResponse(data=[Embedding(embedding=[0.1, 0.2, 0.3], index=0, object="embedding")], model="voyage-test")
    monkeypatch.setattr(
        litellm, "aembedding",
        AsyncMock(side_effect=[litellm.exceptions.APIConnectionError(message="refused", llm_provider="openai", model="m"), answer]),
    )
    assert await get_embeddings_with_fallback(["hello"], providers=["openai", "voyage"]) == [[0.1, 0.2, 0.3]]
