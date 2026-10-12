"""Found against a real local Ollama (tests/llm_optin/test_local_llm_providers.py): LiteLLM's connection, not-found and 5xx errors do not inherit
from `litellm.exceptions.APIError`, so they escaped `chat_completion` as raw LiteLLM exceptions (the provider fallback and the agent's
`except LLMError` never saw them); streaming had no mapping at all; and `openai_compatible` with no key made the OpenAI client refuse to start.
These tests pin the fixes without any network."""

from unittest.mock import AsyncMock

import litellm
import pytest

from api.config import settings
from api.services.llm_providers import (
    LLMError,
    LLMProviderError,
    LLMRateLimitError,
    _provider_kwargs,
    chat_completion,
    chat_completion_stream,
    chat_completion_stream_with_tools,
    chat_completion_with_fallback,
)

MESSAGES = [{"role": "user", "content": "hi"}]


@pytest.fixture(autouse=True)
def local_endpoints(monkeypatch):
    monkeypatch.setattr(settings, "OLLAMA_BASE_URL", "http://127.0.0.1:11434")
    monkeypatch.setattr(settings, "OPENAI_COMPATIBLE_BASE_URL", "http://127.0.0.1:11434/v1")
    monkeypatch.setattr(settings, "OPENAI_COMPATIBLE_API_KEY", "")
    monkeypatch.setattr(settings, "LLM_MAX_RETRIES", 0)


def _errors():
    return [
        litellm.exceptions.APIConnectionError(message="refused", llm_provider="ollama", model="m"),
        litellm.exceptions.InternalServerError(message="boom", llm_provider="ollama", model="m"),
        litellm.exceptions.ServiceUnavailableError(message="down", llm_provider="ollama", model="m"),
        litellm.exceptions.NotFoundError(message="model not found", llm_provider="ollama", model="m"),
        litellm.exceptions.BadRequestError(message="bad", llm_provider="ollama", model="m"),
    ]


@pytest.mark.parametrize("error", _errors(), ids=lambda e: type(e).__name__)
async def test_litellm_connection_and_status_errors_become_llm_errors(monkeypatch, error):
    monkeypatch.setattr(litellm, "acompletion", AsyncMock(side_effect=error))
    with pytest.raises(LLMProviderError):
        await chat_completion(MESSAGES, provider="ollama", model="m")


async def test_the_fallback_moves_on_when_the_first_provider_is_down(monkeypatch):
    from litellm.types.utils import Choices, Message, ModelResponse

    answer = ModelResponse(choices=[Choices(message=Message(content="ok", role="assistant"), index=0, finish_reason="stop")])
    monkeypatch.setattr(litellm, "acompletion", AsyncMock(side_effect=[litellm.exceptions.APIConnectionError(message="refused", llm_provider="ollama", model="m"), answer]))
    assert await chat_completion_with_fallback(MESSAGES, ["ollama", "openai_compatible"], max_retries=0) == "ok"


async def test_a_transient_server_error_is_retried(monkeypatch):
    from litellm.types.utils import Choices, Message, ModelResponse

    answer = ModelResponse(choices=[Choices(message=Message(content="back", role="assistant"), index=0, finish_reason="stop")])
    mock = AsyncMock(side_effect=[litellm.exceptions.InternalServerError(message="boom", llm_provider="ollama", model="m"), answer])
    monkeypatch.setattr(litellm, "acompletion", mock)
    monkeypatch.setattr("api.services.llm_providers.asyncio.sleep", AsyncMock())
    assert await chat_completion(MESSAGES, provider="ollama", model="m", max_retries=1) == "back"
    assert mock.call_count == 2


@pytest.mark.parametrize("streamer", [chat_completion_stream, chat_completion_stream_with_tools])
async def test_streaming_errors_become_llm_errors(monkeypatch, streamer):
    monkeypatch.setattr(litellm, "acompletion", AsyncMock(side_effect=litellm.exceptions.APIConnectionError(message="refused", llm_provider="ollama", model="m")))
    with pytest.raises(LLMError):
        async for _ in streamer(MESSAGES, provider="ollama", model="m"):
            pass


async def test_streaming_keeps_the_error_kind(monkeypatch):
    monkeypatch.setattr(litellm, "acompletion", AsyncMock(side_effect=litellm.exceptions.RateLimitError(message="slow down", llm_provider="ollama", model="m")))
    with pytest.raises(LLMRateLimitError):
        async for _ in chat_completion_stream(MESSAGES, provider="ollama", model="m"):
            pass


def test_openai_compatible_without_a_key_still_gets_one_for_the_client():
    kwargs = _provider_kwargs("openai_compatible", "qwen2.5:3b")
    assert kwargs["api_key"]
    assert kwargs["api_base"] == "http://127.0.0.1:11434/v1"


def test_a_configured_key_is_not_replaced(monkeypatch):
    monkeypatch.setattr(settings, "OPENAI_COMPATIBLE_API_KEY", "real-key")
    assert _provider_kwargs("openai_compatible", "m")["api_key"] == "real-key"
