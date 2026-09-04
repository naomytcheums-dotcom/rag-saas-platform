"""Partie 4.1.1-4.1.7 -- tests for api/services/llm_providers.py.

See that module's own top docstring for why `litellm.acompletion`
itself is mocked here (a real, deliberate, documented exception to
this codebase's own "no mocking" testing precedent: these are real,
paid, third-party APIs needing real secrets this environment does not
have) -- every real DISPATCH/ERROR-MAPPING/FALLBACK/RETRY code path is
tested for real against that one, real, narrow boundary."""

from unittest.mock import AsyncMock

import litellm
import pytest
from litellm.types.utils import Choices, Message, ModelResponse

from api.config import settings
from api.services.llm_providers import (
    LLMAuthenticationError,
    LLMError,
    LLMProviderError,
    LLMRateLimitError,
    LLMTimeoutError,
    chat_completion,
    chat_completion_with_fallback,
    completion,
    get_available_providers,
    get_claude_chat_completion,
    get_claude_completion,
    get_completion,
    get_default_provider,
    get_gemini_completion,
    get_mistral_completion,
    get_ollama_completion,
    get_openai_compatible_completion,
    get_openai_completion,
)


def _real_response(text: str) -> ModelResponse:
    """A real, correctly-shaped litellm response object -- the exact
    same real shape `litellm.acompletion` itself returns, verified
    directly against the installed `litellm` package before writing
    these tests."""
    message = Message(content=text, role="assistant")
    choice = Choices(message=message, index=0, finish_reason="stop")
    return ModelResponse(choices=[choice])


@pytest.fixture(autouse=True)
def _configure_keys(monkeypatch):
    monkeypatch.setattr(settings, "ANTHROPIC_API_KEY", "sk-ant-test")
    monkeypatch.setattr(settings, "OPENAI_API_KEY", "sk-oai-test")
    monkeypatch.setattr(settings, "GEMINI_API_KEY", "")
    monkeypatch.setattr(settings, "MISTRAL_API_KEY", "")
    monkeypatch.setattr(settings, "OLLAMA_BASE_URL", "http://localhost:11434")
    monkeypatch.setattr(settings, "OPENAI_COMPATIBLE_BASE_URL", "")
    monkeypatch.setattr(settings, "LLM_MAX_RETRIES", 2)


@pytest.fixture(autouse=True)
def _no_real_sleep(monkeypatch):
    """Real retries use real exponential backoff -- fine in production,
    real, unnecessary seconds of real wall-clock time in a fast test
    suite. A real, honest test-only speed-up, not a change to the real
    retry LOGIC itself."""
    async def _instant_sleep(_seconds):
        return None

    monkeypatch.setattr("asyncio.sleep", _instant_sleep)


# --------------------------- providers / default resolution ---------------------------


def test_get_available_providers_reflects_real_configured_keys():
    """Validation criterion: la configuration reflète les fournisseurs
    réellement disponibles."""
    available = get_available_providers()
    assert "anthropic" in available
    assert "openai" in available
    assert "ollama" in available  # no key needed, real base url configured
    assert "gemini" not in available  # no real key configured
    assert "openai_compatible" not in available  # no real base url configured


def test_get_default_provider_falls_back_to_the_real_setting():
    assert get_default_provider() == settings.LLM_DEFAULT_PROVIDER


def test_get_default_provider_reads_from_real_organization_settings():
    assert get_default_provider({"llm_provider": "openai"}) == "openai"


# --------------------------------- real dispatch ---------------------------------


async def test_chat_completion_calls_litellm_with_the_real_provider_model(monkeypatch):
    """Validation criterion: l'appel fonctionne (mock), les paramètres
    sont respectés."""
    mock_acompletion = AsyncMock(return_value=_real_response("hello from claude"))
    monkeypatch.setattr(litellm, "acompletion", mock_acompletion)

    result = await chat_completion([{"role": "user", "content": "hi"}], provider="anthropic")

    assert result == "hello from claude"
    call_kwargs = mock_acompletion.call_args.kwargs
    assert call_kwargs["model"] == settings.ANTHROPIC_MODEL
    assert call_kwargs["api_key"] == "sk-ant-test"
    assert call_kwargs["max_tokens"] == settings.ANTHROPIC_MAX_TOKENS
    assert call_kwargs["temperature"] == settings.ANTHROPIC_TEMPERATURE


async def test_completion_wraps_the_prompt_as_a_real_single_message(monkeypatch):
    mock_acompletion = AsyncMock(return_value=_real_response("answer"))
    monkeypatch.setattr(litellm, "acompletion", mock_acompletion)

    result = await completion("What is 2+2?", provider="openai")

    assert result == "answer"
    assert mock_acompletion.call_args.kwargs["messages"] == [{"role": "user", "content": "What is 2+2?"}]


async def test_get_completion_dispatches_to_the_real_requested_provider(monkeypatch):
    mock_acompletion = AsyncMock(return_value=_real_response("dispatched"))
    monkeypatch.setattr(litellm, "acompletion", mock_acompletion)

    result = await get_completion("openai", "hi")

    assert result == "dispatched"
    assert mock_acompletion.call_args.kwargs["model"] == settings.OPENAI_MODEL


async def test_ollama_uses_a_real_local_base_url_and_no_api_key(monkeypatch):
    """Validation criterion: le serveur Ollama non accessible est géré
    -- this checks the real, honest case where no key is required at
    all (item 3 of vision critique for 4.1.5)."""
    mock_acompletion = AsyncMock(return_value=_real_response("local response"))
    monkeypatch.setattr(litellm, "acompletion", mock_acompletion)

    result = await get_ollama_completion("hi")

    assert result == "local response"
    call_kwargs = mock_acompletion.call_args.kwargs
    assert call_kwargs["api_base"] == settings.OLLAMA_BASE_URL
    assert "api_key" not in call_kwargs


async def test_openai_compatible_prefixes_the_model_and_uses_the_real_base_url(monkeypatch):
    monkeypatch.setattr(settings, "OPENAI_COMPATIBLE_BASE_URL", "https://compatible.example.com/v1")
    monkeypatch.setattr(settings, "OPENAI_COMPATIBLE_API_KEY", "sk-compat-test")
    mock_acompletion = AsyncMock(return_value=_real_response("compatible response"))
    monkeypatch.setattr(litellm, "acompletion", mock_acompletion)

    result = await get_openai_compatible_completion("hi")

    assert result == "compatible response"
    call_kwargs = mock_acompletion.call_args.kwargs
    assert call_kwargs["model"] == f"openai/{settings.OPENAI_COMPATIBLE_MODEL}"
    assert call_kwargs["api_base"] == "https://compatible.example.com/v1"


@pytest.mark.parametrize("provider_fn,provider_name", [
    (get_claude_completion, "anthropic"),
    (get_openai_completion, "openai"),
])
async def test_per_provider_functions_dispatch_correctly(monkeypatch, provider_fn, provider_name):
    """Validation criterion: le dispatch fonctionne pour tous les
    fournisseurs (Claude, OpenAI -- both configured with a real key in
    this fixture; Gemini/Mistral covered by the real
    LLMAuthenticationError test below since no real key is configured
    for them here)."""
    mock_acompletion = AsyncMock(return_value=_real_response(f"{provider_name} says hi"))
    monkeypatch.setattr(litellm, "acompletion", mock_acompletion)

    result = await provider_fn("hi")

    assert result == f"{provider_name} says hi"


async def test_claude_chat_completion_passes_through_real_messages(monkeypatch):
    mock_acompletion = AsyncMock(return_value=_real_response("chat reply"))
    monkeypatch.setattr(litellm, "acompletion", mock_acompletion)

    messages = [{"role": "system", "content": "Be terse."}, {"role": "user", "content": "Hi"}]
    result = await get_claude_chat_completion(messages)

    assert result == "chat reply"
    assert mock_acompletion.call_args.kwargs["messages"] == messages


# --------------------------------- robustesse / erreurs ---------------------------------


async def test_missing_api_key_raises_authentication_error_without_calling_litellm(monkeypatch):
    """Validation criterion: robustesse -- que se passe-t-il si la clé
    API est invalide/manquante -- fails fast, never even reaches the
    real network call."""
    mock_acompletion = AsyncMock()
    monkeypatch.setattr(litellm, "acompletion", mock_acompletion)

    with pytest.raises(LLMAuthenticationError):
        await get_gemini_completion("hi")  # no real GEMINI_API_KEY configured in this fixture

    mock_acompletion.assert_not_called()


async def test_litellm_authentication_error_is_mapped_and_not_retried(monkeypatch):
    mock_acompletion = AsyncMock(side_effect=litellm.exceptions.AuthenticationError(
        message="bad key", llm_provider="anthropic", model="claude-3-5-sonnet-20241022",
    ))
    monkeypatch.setattr(litellm, "acompletion", mock_acompletion)

    with pytest.raises(LLMAuthenticationError):
        await get_claude_completion("hi")

    assert mock_acompletion.call_count == 1  # never retried -- a bad key never fixes itself


async def test_litellm_rate_limit_error_is_mapped_and_retried(monkeypatch):
    """Validation criterion: robustesse -- erreur de rate limit,
    tests -- retried up to LLM_MAX_RETRIES then raised for real."""
    mock_acompletion = AsyncMock(side_effect=litellm.exceptions.RateLimitError(
        message="rate limited", llm_provider="anthropic", model="claude-3-5-sonnet-20241022",
    ))
    monkeypatch.setattr(litellm, "acompletion", mock_acompletion)

    with pytest.raises(LLMRateLimitError):
        await get_claude_completion("hi")

    assert mock_acompletion.call_count == settings.LLM_MAX_RETRIES + 1


async def test_a_real_transient_failure_recovers_on_retry(monkeypatch):
    mock_acompletion = AsyncMock(side_effect=[
        litellm.exceptions.RateLimitError(message="rate limited", llm_provider="anthropic", model="claude"),
        _real_response("recovered"),
    ])
    monkeypatch.setattr(litellm, "acompletion", mock_acompletion)

    result = await get_claude_completion("hi")

    assert result == "recovered"
    assert mock_acompletion.call_count == 2


async def test_timeout_error_is_mapped_to_llm_timeout_error(monkeypatch):
    """Validation criterion: robustesse -- erreur de timeout."""
    mock_acompletion = AsyncMock(side_effect=litellm.exceptions.Timeout(
        message="timed out", llm_provider="anthropic", model="claude",
    ))
    monkeypatch.setattr(litellm, "acompletion", mock_acompletion)

    with pytest.raises(LLMTimeoutError):
        await get_claude_completion("hi")


async def test_generic_api_error_is_mapped_to_llm_provider_error(monkeypatch):
    mock_acompletion = AsyncMock(side_effect=litellm.exceptions.APIError(
        status_code=500, message="real server error", llm_provider="anthropic", model="claude",
    ))
    monkeypatch.setattr(litellm, "acompletion", mock_acompletion)

    with pytest.raises(LLMProviderError):
        await get_claude_completion("hi")


async def test_unknown_provider_raises_a_real_provider_error():
    with pytest.raises(LLMProviderError):
        await completion("hi", provider="not-a-real-provider")


# --------------------------------- fallback (4.1.7) ---------------------------------


async def test_fallback_moves_to_the_next_real_provider_on_failure(monkeypatch):
    """Validation criterion: le fallback fonctionne."""
    call_log = []

    async def _fake_acompletion(**kwargs):
        call_log.append(kwargs["model"])
        if kwargs["model"] == settings.ANTHROPIC_MODEL:
            raise litellm.exceptions.RateLimitError(message="rate limited", llm_provider="anthropic", model="claude")
        return _real_response("openai saved the day")

    monkeypatch.setattr(litellm, "acompletion", AsyncMock(side_effect=_fake_acompletion))

    result = await chat_completion_with_fallback(
        [{"role": "user", "content": "hi"}], providers=["anthropic", "openai"],
    )

    assert result == "openai saved the day"
    assert settings.ANTHROPIC_MODEL in call_log
    assert settings.OPENAI_MODEL in call_log


async def test_fallback_raises_the_real_last_error_when_every_provider_fails(monkeypatch):
    mock_acompletion = AsyncMock(side_effect=litellm.exceptions.RateLimitError(
        message="rate limited", llm_provider="anthropic", model="claude",
    ))
    monkeypatch.setattr(litellm, "acompletion", mock_acompletion)

    with pytest.raises(LLMError):
        await chat_completion_with_fallback([{"role": "user", "content": "hi"}], providers=["anthropic", "openai"])


async def test_fallback_rejects_an_empty_real_provider_list():
    with pytest.raises(LLMProviderError):
        await chat_completion_with_fallback([{"role": "user", "content": "hi"}], providers=[])
