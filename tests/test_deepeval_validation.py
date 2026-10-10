"""
api/services/deepeval_validation.py -- `metric.a_measure` makes a real,
paid LLM call under the hood (DeepEval's own real judge-LLM prompting).
Same real, documented exception as every other real-paid-LLM-call
module in this session (tests/test_graph_rag.py, tests/test_prompt_optimization.py,
tests/test_beeai_orchestrator.py): `a_measure` is mocked at its own
clean, already-tested boundary, never `LiteLLMModel`/`LLMTestCase`
themselves -- those are real, used exactly as verified directly against
the installed `deepeval` package before writing this module."""

import uuid
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from api.services.deepeval_validation import cross_validate_answer


def _make_question(expected_answer: str | None = "Paris is the capital of France."):
    question = MagicMock()
    question.question = "What is the capital of France?"
    question.expected_answer = expected_answer
    return question


def _patch_metric(path: str, score: float, reason: str):
    mock_instance = MagicMock()
    mock_instance.a_measure = AsyncMock(return_value=score)
    mock_instance.reason = reason
    return patch(path, return_value=mock_instance)


async def test_cross_validate_answer_uses_this_organizations_real_configured_model(monkeypatch):
    """Validation criterion: DeepEval must run against THIS
    organization's own real, configured provider/model -- never its
    own independent OpenAI default."""
    monkeypatch.setattr("api.services.llm_providers.settings.ANTHROPIC_API_KEY", "sk-ant-test")
    monkeypatch.setattr("api.services.llm_providers.settings.ANTHROPIC_MODEL", "claude-3-5-sonnet-20241022")

    captured_model_kwargs = {}

    class FakeLiteLLMModel:
        def __init__(self, model=None, api_key=None, **kwargs):
            captured_model_kwargs["model"] = model
            captured_model_kwargs["api_key"] = api_key

    question = _make_question(expected_answer=None)

    with patch("deepeval.models.LiteLLMModel", FakeLiteLLMModel), \
         _patch_metric("deepeval.metrics.FaithfulnessMetric", 0.9, "Faithful to the context."), \
         _patch_metric("deepeval.metrics.AnswerRelevancyMetric", 0.85, "Relevant to the question."):
        result = await cross_validate_answer(
            question, "Paris.", ["France's capital is Paris."], "anthropic", "claude-3-5-sonnet-20241022",
        )

    assert captured_model_kwargs["model"] == "claude-3-5-sonnet-20241022"
    assert captured_model_kwargs["api_key"] == "sk-ant-test"
    assert result["faithfulness"] == {"score": 0.9, "reason": "Faithful to the context."}
    assert result["answer_relevancy"] == {"score": 0.85, "reason": "Relevant to the question."}


async def test_cross_validate_answer_skips_ground_truth_dependent_metrics_without_an_expected_answer(monkeypatch):
    """Real, honest behavior: contextual_precision/contextual_recall
    are real, ground-truth-dependent DeepEval metrics -- a question
    with no real expected_answer gets exactly the 2 metrics honestly
    computable, never a fabricated score for the other 2."""
    monkeypatch.setattr("api.services.llm_providers.settings.ANTHROPIC_API_KEY", "sk-ant-test")  # the provider key must exist, as on a dev machine
    question = _make_question(expected_answer=None)

    with patch("deepeval.models.LiteLLMModel", MagicMock()), \
         _patch_metric("deepeval.metrics.FaithfulnessMetric", 0.9, "ok"), \
         _patch_metric("deepeval.metrics.AnswerRelevancyMetric", 0.8, "ok"):
        result = await cross_validate_answer(question, "Paris.", ["ctx"], "anthropic")

    assert set(result.keys()) == {"faithfulness", "answer_relevancy"}


async def test_cross_validate_answer_includes_ground_truth_dependent_metrics_when_available(monkeypatch):
    """Real, honest opposite case: a question WITH a real expected
    answer gets all 4 real metrics, including the 2 that genuinely
    need ground truth to compute."""
    monkeypatch.setattr("api.services.llm_providers.settings.ANTHROPIC_API_KEY", "sk-ant-test")  # the provider key must exist, as on a dev machine
    question = _make_question(expected_answer="Paris is the capital of France.")

    with patch("deepeval.models.LiteLLMModel", MagicMock()), \
         _patch_metric("deepeval.metrics.FaithfulnessMetric", 0.9, "ok"), \
         _patch_metric("deepeval.metrics.AnswerRelevancyMetric", 0.8, "ok"), \
         _patch_metric("deepeval.metrics.ContextualPrecisionMetric", 0.7, "ok"), \
         _patch_metric("deepeval.metrics.ContextualRecallMetric", 0.75, "ok"):
        result = await cross_validate_answer(question, "Paris.", ["ctx"], "anthropic")

    assert set(result.keys()) == {"faithfulness", "answer_relevancy", "contextual_precision", "contextual_recall"}
    assert result["contextual_precision"]["score"] == 0.7
    assert result["contextual_recall"]["score"] == 0.75


async def test_cross_validate_answer_raises_a_real_honest_error_when_deepeval_is_not_installed(monkeypatch):
    import builtins

    real_import = builtins.__import__

    def _fake_import(name, *args, **kwargs):
        if name == "deepeval.metrics":
            raise ImportError("No module named 'deepeval'")
        return real_import(name, *args, **kwargs)

    monkeypatch.setattr(builtins, "__import__", _fake_import)

    from api.services.deepeval_validation import DeepEvalNotAvailableError

    question = _make_question()
    with pytest.raises(DeepEvalNotAvailableError):
        await cross_validate_answer(question, "Paris.", ["ctx"], "anthropic")
