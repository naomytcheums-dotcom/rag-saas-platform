"""Partie 7.3 -- multi-model comparisons and A/B testing. Fast SQLite
suite; litellm/search_with_context mocked at the same boundary as
tests/test_evaluation_results.py."""

import uuid
from unittest.mock import AsyncMock

import litellm
import pytest
from litellm.types.utils import Choices, Message, ModelResponse

from api.config import settings
from api.models.evaluation import EvaluationDataset, EvaluationQuestion
from api.models.organization import Organization
from api.services.evaluation_comparisons import _sign_test_p_value, run_ab_test, run_multi_model_comparison
from api.services.question_sets import add_question_to_set, create_question_set


def _real_response(text: str) -> ModelResponse:
    message = Message(content=text, role="assistant")
    choice = Choices(message=message, index=0, finish_reason="stop")
    return ModelResponse(choices=[choice])


@pytest.fixture(autouse=True)
def _configure_key(monkeypatch):
    monkeypatch.setattr(settings, "ANTHROPIC_API_KEY", "sk-ant-test")


async def _make_org(db_session, name):
    org = Organization(name=name, slug=f"{name.lower().replace(' ', '-')}-{uuid.uuid4().hex[:8]}")
    db_session.add(org)
    await db_session.flush()
    return org


async def _make_question_set(db_session, org_id, question_count=2):
    dataset = EvaluationDataset(organization_id=org_id, name="D")
    db_session.add(dataset)
    await db_session.flush()
    question_set = await create_question_set(db_session, dataset.id, "S")
    questions = []
    for i in range(question_count):
        question = EvaluationQuestion(dataset_id=dataset.id, question=f"Question {i}?")
        db_session.add(question)
        await db_session.flush()
        await add_question_to_set(db_session, question_set.id, question.id)
        questions.append(question)
    await db_session.commit()
    return question_set, questions


# --------------------------------------- _sign_test_p_value --


def test_sign_test_p_value_is_honestly_one_with_no_real_evidence():
    """Validation criterion: robustesse -- aucune vraie question non-tied."""
    assert _sign_test_p_value(0, 0) == 1.0


def test_sign_test_p_value_is_low_for_a_real_unanimous_result():
    """Validation criterion: A/B testing -- signification statistique."""
    assert _sign_test_p_value(0, 10) < 0.01


def test_sign_test_p_value_is_high_for_a_real_even_split():
    assert _sign_test_p_value(5, 5) == 1.0


# --------------------------------------- run_multi_model_comparison --


async def test_run_multi_model_comparison_ranks_real_configs(monkeypatch, db_session):
    """Validation criterion: comparaisons multi-modèles fonctionnent."""
    monkeypatch.setattr("api.services.evaluation_results.search_with_context", AsyncMock(return_value=[]))
    responses = iter(["A weak answer.", "A much better, more complete and on-topic answer to the real question asked."] * 5)
    monkeypatch.setattr(litellm, "acompletion", AsyncMock(side_effect=lambda **kwargs: _real_response(next(responses))))

    org = await _make_org(db_session, "Comparison Org")
    await db_session.commit()
    question_set, questions = await _make_question_set(db_session, org.id, question_count=2)

    comparison = await run_multi_model_comparison(db_session, question_set.id, [{"temperature": 0.1}, {"temperature": 0.9}])
    await db_session.commit()

    assert comparison["sample_size"] == 2
    assert len(comparison["configs"]) == 2
    assert len(comparison["configs"][0]["result_ids"]) == 2
    assert comparison["rank_metric"] == settings.EVALUATION_DEFAULT_COMPARISON_METRIC
    assert set(comparison["ranking"]) == {0, 1}
    assert "answer_relevance" in comparison["configs"][0]["metrics"]


async def test_run_multi_model_comparison_is_honest_with_no_real_questions(db_session):
    """Validation criterion: robustesse -- ensemble de questions vide."""
    org = await _make_org(db_session, "Comparison Empty Org")
    await db_session.commit()
    dataset = EvaluationDataset(organization_id=org.id, name="D")
    db_session.add(dataset)
    await db_session.flush()
    question_set = await create_question_set(db_session, dataset.id, "Empty Set")
    await db_session.commit()

    comparison = await run_multi_model_comparison(db_session, question_set.id, [{}])
    assert comparison["sample_size"] == 0
    assert comparison["configs"][0]["result_ids"] == []
    assert comparison["configs"][0]["metrics"]["mrr"] == {"metric": "mrr", "count": 0, "average": None, "min": None, "max": None}


# --------------------------------------- run_ab_test --


async def test_run_ab_test_is_honest_when_the_requested_metric_key_does_not_exist(monkeypatch, db_session):
    """Validation criterion: robustesse -- une métrique inconnue est
    honnêtement ignorée (sample_size=0), jamais une égalité fabriquée."""
    monkeypatch.setattr("api.services.evaluation_results.search_with_context", AsyncMock(return_value=[]))
    monkeypatch.setattr(litellm, "acompletion", AsyncMock(return_value=_real_response("An answer.")))

    org = await _make_org(db_session, "AB Test Org")
    await db_session.commit()
    question_set, questions = await _make_question_set(db_session, org.id, question_count=3)

    result = await run_ab_test(db_session, question_set.id, {"temperature": 0.1}, {"temperature": 0.9}, metric="latency_ms")
    await db_session.commit()

    assert result["sample_size"] == 0  # latency_ms n'est pas une vraie clé de metrics -- honnêtement ignoré
    assert result["p_value"] == 1.0
    assert result["significant"] is False


async def test_run_ab_test_defaults_to_the_real_configured_metric(monkeypatch, db_session):
    """Validation criterion: A/B testing fonctionne."""
    monkeypatch.setattr("api.services.evaluation_results.search_with_context", AsyncMock(return_value=[]))
    monkeypatch.setattr(litellm, "acompletion", AsyncMock(return_value=_real_response("An answer.")))

    org = await _make_org(db_session, "AB Test Default Org")
    await db_session.commit()
    question_set, questions = await _make_question_set(db_session, org.id, question_count=2)

    result = await run_ab_test(db_session, question_set.id, {}, {})
    await db_session.commit()

    assert result["metric"] == settings.EVALUATION_DEFAULT_COMPARISON_METRIC
    assert result["sample_size"] == 2
    assert result["wins_a"] + result["wins_b"] + result["ties"] == 2
