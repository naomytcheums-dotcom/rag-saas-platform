"""Partie 7.2.14 -- token usage. Fast SQLite suite; litellm/
search_with_context mocked at the same boundary as
tests/test_evaluation_results.py, with a real litellm `Usage` object
attached so `chat_completion_with_usage`'s own real usage-capture path
is genuinely exercised."""

import uuid
from unittest.mock import AsyncMock

import litellm
from litellm.types.utils import Choices, Message, ModelResponse, Usage

from api.config import settings
from api.models.evaluation import EvaluationDataset, EvaluationQuestion
from api.models.organization import Organization
from api.services.evaluation_results import run_evaluation
from api.services.token_usage import estimate_token_usage, measure_token_usage


def _real_response(text: str, usage: Usage | None = None) -> ModelResponse:
    message = Message(content=text, role="assistant")
    choice = Choices(message=message, index=0, finish_reason="stop")
    response = ModelResponse(choices=[choice])
    if usage is not None:
        response.usage = usage
    return response


async def _make_org(db_session, name):
    org = Organization(name=name, slug=f"{name.lower().replace(' ', '-')}-{uuid.uuid4().hex[:8]}")
    db_session.add(org)
    await db_session.flush()
    return org


async def _make_question(db_session, org_id):
    dataset = EvaluationDataset(organization_id=org_id, name="D")
    db_session.add(dataset)
    await db_session.flush()
    question = EvaluationQuestion(dataset_id=dataset.id, question="Why is the sky blue?")
    db_session.add(question)
    await db_session.commit()
    return dataset, question


def test_estimate_token_usage_is_a_real_documented_approximation():
    """Validation criterion: robustesse -- estimation quand les tokens
    ne sont pas disponibles."""
    result = estimate_token_usage("a" * 40, "b" * 20, model="test-model")
    assert result["estimated"] is True
    assert result["prompt_tokens"] == round(40 / settings.TOKEN_USAGE_ESTIMATE_CHARS_PER_TOKEN)
    assert result["total_tokens"] == result["prompt_tokens"] + result["completion_tokens"]


async def test_run_evaluation_captures_real_provider_reported_usage(monkeypatch, db_session):
    """Validation criterion: la mesure de Token usage fonctionne."""
    monkeypatch.setattr(settings, "ANTHROPIC_API_KEY", "sk-ant-test")
    monkeypatch.setattr("api.services.evaluation_results.search_with_context", AsyncMock(return_value=[]))
    usage = Usage(prompt_tokens=42, completion_tokens=8, total_tokens=50)
    monkeypatch.setattr(litellm, "acompletion", AsyncMock(return_value=_real_response("An answer.", usage=usage)))

    org = await _make_org(db_session, "Token Usage Org")
    await db_session.commit()
    _dataset, question = await _make_question(db_session, org.id)

    result = await run_evaluation(db_session, question.id)
    await db_session.commit()

    token_usage = result.metrics["token_usage"]
    assert token_usage["prompt_tokens"] == 42
    assert token_usage["completion_tokens"] == 8
    assert token_usage["total_tokens"] == 50
    assert token_usage["estimated"] is False
    assert result.metrics["total_tokens"] == 50


async def test_run_evaluation_falls_back_to_a_real_estimate_with_no_real_provider_usage(monkeypatch, db_session):
    """Validation criterion: robustesse -- tokens non disponibles."""
    monkeypatch.setattr(settings, "ANTHROPIC_API_KEY", "sk-ant-test")
    monkeypatch.setattr("api.services.evaluation_results.search_with_context", AsyncMock(return_value=[]))
    monkeypatch.setattr(litellm, "acompletion", AsyncMock(return_value=_real_response("An answer.", usage=None)))

    org = await _make_org(db_session, "Token Usage Estimate Org")
    await db_session.commit()
    _dataset, question = await _make_question(db_session, org.id)

    result = await run_evaluation(db_session, question.id)
    await db_session.commit()

    assert result.metrics["token_usage"]["estimated"] is True


async def test_run_evaluation_forces_the_real_estimate_when_configured(monkeypatch, db_session):
    monkeypatch.setattr(settings, "ANTHROPIC_API_KEY", "sk-ant-test")
    monkeypatch.setattr(settings, "TOKEN_USAGE_ESTIMATE_ONLY", True)
    monkeypatch.setattr("api.services.evaluation_results.search_with_context", AsyncMock(return_value=[]))
    usage = Usage(prompt_tokens=42, completion_tokens=8, total_tokens=50)
    monkeypatch.setattr(litellm, "acompletion", AsyncMock(return_value=_real_response("An answer.", usage=usage)))

    org = await _make_org(db_session, "Token Usage Force Estimate Org")
    await db_session.commit()
    _dataset, question = await _make_question(db_session, org.id)

    result = await run_evaluation(db_session, question.id)
    await db_session.commit()

    assert result.metrics["token_usage"]["estimated"] is True


async def test_run_evaluation_skips_real_token_tracking_when_disabled(monkeypatch, db_session):
    monkeypatch.setattr(settings, "ANTHROPIC_API_KEY", "sk-ant-test")
    monkeypatch.setattr(settings, "TOKEN_USAGE_TRACKING_ENABLED", False)
    monkeypatch.setattr("api.services.evaluation_results.search_with_context", AsyncMock(return_value=[]))
    monkeypatch.setattr(litellm, "acompletion", AsyncMock(return_value=_real_response("An answer.")))

    org = await _make_org(db_session, "Token Usage Disabled Org")
    await db_session.commit()
    _dataset, question = await _make_question(db_session, org.id)

    result = await run_evaluation(db_session, question.id)
    await db_session.commit()

    assert "token_usage" not in result.metrics


async def test_measure_token_usage_reuses_run_evaluation(monkeypatch, db_session):
    monkeypatch.setattr(settings, "ANTHROPIC_API_KEY", "sk-ant-test")
    monkeypatch.setattr("api.services.evaluation_results.search_with_context", AsyncMock(return_value=[]))
    usage = Usage(prompt_tokens=10, completion_tokens=5, total_tokens=15)
    monkeypatch.setattr(litellm, "acompletion", AsyncMock(return_value=_real_response("An answer.", usage=usage)))

    org = await _make_org(db_session, "Measure Token Usage Org")
    await db_session.commit()
    _dataset, question = await _make_question(db_session, org.id)

    token_usage = await measure_token_usage(db_session, question.id)
    await db_session.commit()

    assert token_usage["total_tokens"] == 15


async def test_measure_token_usage_is_honestly_none_for_an_unknown_question(db_session):
    """Validation criterion: robustesse."""
    assert await measure_token_usage(db_session, uuid.uuid4()) is None
