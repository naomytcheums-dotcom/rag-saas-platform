"""Ollama models go through litellm's `ollama_chat/` route (/api/chat): on `ollama/` (/api/generate) a streamed tool call came back as plain text
(checked against a real Ollama server by tests/llm_optin/test_local_agents_ollama.py)."""

import litellm
import pytest

from api.config import settings
from api.services.llm_providers import _provider_kwargs, to_litellm_model


@pytest.mark.parametrize("stored", ["llama3.1", "ollama/llama3.1", "ollama_chat/llama3.1"])
def test_every_stored_spelling_is_sent_to_the_chat_endpoint(stored):
    assert to_litellm_model("ollama", stored) == "ollama_chat/llama3.1"


def test_the_configured_default_model_is_sent_to_the_chat_endpoint(monkeypatch):
    monkeypatch.setattr(settings, "OLLAMA_MODEL", "ollama/llama3.1")

    kwargs = _provider_kwargs("ollama", None)

    assert kwargs["model"] == "ollama_chat/llama3.1"
    assert litellm.get_llm_provider(kwargs["model"])[1] == "ollama_chat"


def test_a_model_name_with_a_tag_keeps_it():
    assert to_litellm_model("ollama", "qwen2.5:7b") == "ollama_chat/qwen2.5:7b"


def test_other_providers_are_untouched():
    assert to_litellm_model("mistral", "mistral-small-latest") == "mistral/mistral-small-latest"
    assert to_litellm_model("openai_compatible", "ollama/llama3.1") == "ollama/llama3.1"
