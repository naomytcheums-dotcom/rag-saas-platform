"""Partie 5.4.3 -- LLM workflow block. Real litellm.acompletion mock,
same boundary as tests/test_llm_providers.py and
tests/test_agent_orchestrator.py."""

from unittest.mock import AsyncMock

import litellm
import pytest
from litellm.types.utils import Choices, Message, ModelResponse

from api.config import settings
from api.services.workflow_block_llm import (
    execute_llm_block, get_available_llm_models, render_llm_prompt, validate_llm_config,
)
from api.services.workflow_blocks import WorkflowBlockError


def _real_response(text: str) -> ModelResponse:
    message = Message(content=text, role="assistant")
    choice = Choices(message=message, index=0, finish_reason="stop")
    return ModelResponse(choices=[choice])


@pytest.fixture(autouse=True)
def _configure_key(monkeypatch):
    monkeypatch.setattr(settings, "ANTHROPIC_API_KEY", "sk-ant-test")


# --------------------------------------- validate_llm_config / render_llm_prompt --


def test_validate_llm_config_accepts_a_real_valid_config():
    validate_llm_config({"user_prompt": "hello {{name}}"})


def test_validate_llm_config_rejects_a_missing_user_prompt():
    """Validation criterion: la validation fonctionne."""
    with pytest.raises(WorkflowBlockError, match="user_prompt"):
        validate_llm_config({})


def test_render_llm_prompt_substitutes_real_variables():
    """Validation criterion: les variables sont remplacées."""
    assert render_llm_prompt("Hello {{input}}!", {"input": "world"}) == "Hello world!"


def test_get_available_llm_models_reuses_the_real_agent_catalog():
    """Validation criterion: cohérence -- réutilise Partie 4.1/5.3.3."""
    from api.services.agent_models import MODEL_CATALOG
    assert get_available_llm_models() == MODEL_CATALOG


# --------------------------------------- execute_llm_block --


async def test_execute_llm_block_returns_a_real_result_under_output_key(monkeypatch):
    """Validation criterion: l'exécution du bloc LLM fonctionne."""
    mock_acompletion = AsyncMock(return_value=_real_response("42"))
    monkeypatch.setattr(litellm, "acompletion", mock_acompletion)

    result = await execute_llm_block({"user_prompt": "What is 6*7?", "output_key": "answer"}, {})
    assert result == {"answer": "42"}


async def test_execute_llm_block_renders_real_template_variables(monkeypatch):
    mock_acompletion = AsyncMock(return_value=_real_response("ok"))
    monkeypatch.setattr(litellm, "acompletion", mock_acompletion)

    await execute_llm_block({"system_prompt": "You help {{org}}.", "user_prompt": "Hi {{name}}"}, {"org": "Acme", "name": "Ada"})

    messages = mock_acompletion.call_args.kwargs["messages"]
    assert messages[0]["content"] == "You help Acme."
    assert messages[1]["content"] == "Hi Ada"


async def test_execute_llm_block_defaults_output_key_to_output(monkeypatch):
    monkeypatch.setattr(litellm, "acompletion", AsyncMock(return_value=_real_response("ok")))
    result = await execute_llm_block({"user_prompt": "hi"}, {})
    assert "output" in result


async def test_execute_llm_block_respects_real_overrides(monkeypatch):
    mock_acompletion = AsyncMock(return_value=_real_response("ok"))
    monkeypatch.setattr(litellm, "acompletion", mock_acompletion)

    await execute_llm_block({"user_prompt": "hi", "temperature": 0.1}, {})
    assert mock_acompletion.call_args.kwargs["temperature"] == 0.1


async def test_execute_llm_block_raises_workflow_block_error_when_unconfigured():
    """Validation criterion: robustesse -- que se passe-t-il si le modèle est indisponible."""
    with pytest.raises(WorkflowBlockError):
        await execute_llm_block({}, {})


async def test_execute_llm_block_wraps_a_real_llm_failure(monkeypatch):
    async def _raise(**kwargs):
        raise litellm.exceptions.AuthenticationError(message="bad key", llm_provider="anthropic", model="claude")

    monkeypatch.setattr(litellm, "acompletion", AsyncMock(side_effect=_raise))

    with pytest.raises(WorkflowBlockError, match="llm_call block failed"):
        await execute_llm_block({"user_prompt": "hi"}, {})
