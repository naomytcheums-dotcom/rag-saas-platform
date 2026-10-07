"""The default chat model (claude-sonnet-5-5) refuses temperature != 1.

A real /chat/stream run failed with `UnsupportedParamsError: claude-sonnet-5-5 does not support temperature=0.7`; the mocked
`litellm.acompletion` used elsewhere never validated params. These tests use LiteLLM's own param mapping, offline."""

import litellm
import pytest
from litellm.utils import get_optional_params

from api.config import settings
from api.services.llm_providers import _provider_kwargs


@pytest.fixture
def anthropic_key(monkeypatch):
    monkeypatch.setattr(settings, "ANTHROPIC_API_KEY", "test-key-not-real")


def test_provider_kwargs_ask_litellm_to_drop_unsupported_params(anthropic_key):
    assert _provider_kwargs("anthropic", "claude-sonnet-5-5")["drop_params"] is True


def test_default_model_call_params_are_accepted_by_litellm(anthropic_key):
    kwargs = _provider_kwargs("anthropic", settings.ANTHROPIC_MODEL)
    params = get_optional_params(
        model=kwargs["model"], custom_llm_provider="anthropic",
        temperature=0.7, max_tokens=kwargs["max_tokens"], drop_params=kwargs["drop_params"],
    )
    assert params["max_tokens"] == kwargs["max_tokens"]
    if litellm.model_cost.get(kwargs["model"], {}).get("supports_sampling_params") is False:
        assert "temperature" not in params


def test_models_that_support_temperature_keep_it(anthropic_key):
    kwargs = _provider_kwargs("anthropic", "claude-haiku-4-5-20251001")
    params = get_optional_params(
        model=kwargs["model"], custom_llm_provider="anthropic", temperature=0.7, max_tokens=10, drop_params=kwargs["drop_params"],
    )
    assert params["temperature"] == 0.7
