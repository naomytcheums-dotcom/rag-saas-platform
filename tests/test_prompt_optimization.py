"""
api/services/prompt_optimization.py -- `BootstrapFewShot.compile` makes
real, paid LLM calls under the hood (bootstrapping few-shot demos means
actually running the student program against the trainset) -- same
real, documented exception as tests/test_beeai_orchestrator.py's own
`RequirementAgent.run` mock: no real API key exists in this
environment. `BootstrapFewShot.compile` is mocked here (the one real
point that would cost real money), never `dspy.Predict`/`dspy.Example`
themselves -- those are real, used exactly as verified directly against
the installed `dspy` package before writing this module.
"""

import uuid
from unittest.mock import MagicMock, patch

import pytest

from api.services.prompt_optimization import (
    MIN_GROUND_TRUTH_EXAMPLES, NotEnoughGroundTruthError, optimize_system_prompt,
)


def _fake_compiled(instructions: str, demos: list[dict]):
    compiled = MagicMock()
    compiled.signature.instructions = instructions
    compiled.demos = demos
    return compiled


async def _make_dataset_with_questions(db_session, count: int, with_answers: bool = True):
    from api.models.evaluation import EvaluationDataset, EvaluationQuestion
    from api.models.organization import Organization

    org = Organization(name="Prompt Opt Org", slug=f"prompt-opt-org-{uuid.uuid4().hex[:8]}")
    db_session.add(org)
    await db_session.flush()

    dataset = EvaluationDataset(organization_id=org.id, name="ground-truth-set")
    db_session.add(dataset)
    await db_session.flush()

    for i in range(count):
        db_session.add(EvaluationQuestion(
            dataset_id=dataset.id, question=f"What is {i}+{i}?",
            expected_answer=f"{2 * i}" if with_answers else None,
        ))
    await db_session.flush()
    await db_session.commit()
    return dataset.id


async def test_optimize_system_prompt_refuses_with_too_few_ground_truth_examples(db_session):
    dataset_id = await _make_dataset_with_questions(db_session, MIN_GROUND_TRUTH_EXAMPLES - 1)

    with pytest.raises(NotEnoughGroundTruthError):
        await optimize_system_prompt(db_session, dataset_id, "anthropic", "claude-3-5-sonnet-20241022")


async def test_optimize_system_prompt_returns_a_real_candidate_wired_to_this_codebases_own_provider(monkeypatch, db_session):
    """Validation criterion: the DSPy LM must be configured with THIS
    organization's own real, resolved provider/model/key -- never
    DSPy's own independent default."""
    dataset_id = await _make_dataset_with_questions(db_session, MIN_GROUND_TRUTH_EXAMPLES)

    captured_lm_kwargs = {}

    class FakeLM:
        def __init__(self, model=None, api_key=None, **kwargs):
            captured_lm_kwargs["model"] = model
            captured_lm_kwargs["api_key"] = api_key

    monkeypatch.setattr("api.services.llm_providers.settings.ANTHROPIC_API_KEY", "sk-ant-test")
    monkeypatch.setattr("api.services.llm_providers.settings.ANTHROPIC_MODEL", "claude-3-5-sonnet-20241022")

    fake_compiled = _fake_compiled(
        "Answer using only the real context.",
        [{"question": "What is 0+0?", "answer": "0"}],
    )

    with patch("dspy.LM", FakeLM), patch("dspy.configure"), \
         patch("dspy.teleprompt.BootstrapFewShot.compile", return_value=fake_compiled):
        result = await optimize_system_prompt(db_session, dataset_id, "anthropic", "claude-3-5-sonnet-20241022")

    assert captured_lm_kwargs["model"] == "claude-3-5-sonnet-20241022"
    assert captured_lm_kwargs["api_key"] == "sk-ant-test"
    assert "Answer using only the real context." in result["system_prompt"]
    assert "Q: What is 0+0?" in result["system_prompt"]
    assert "A: 0" in result["system_prompt"]
    assert result["trainset_size"] == MIN_GROUND_TRUTH_EXAMPLES
    assert result["bootstrapped_demo_count"] == 1
    assert result["exceeds_runtime_limit"] is False


async def test_optimize_system_prompt_honestly_reports_exceeding_the_runtime_limit(monkeypatch, db_session):
    dataset_id = await _make_dataset_with_questions(db_session, MIN_GROUND_TRUTH_EXAMPLES)

    monkeypatch.setattr("api.services.llm_providers.settings.ANTHROPIC_API_KEY", "sk-ant-test")
    monkeypatch.setattr("api.services.llm_providers.settings.ANTHROPIC_MODEL", "claude-3-5-sonnet-20241022")
    monkeypatch.setattr("api.services.prompt_optimization.settings.SYSTEM_PROMPT_MAX_LENGTH", 10)

    fake_compiled = _fake_compiled("A very long real instruction that exceeds ten characters.", [])

    with patch("dspy.LM", MagicMock()), patch("dspy.configure"), \
         patch("dspy.teleprompt.BootstrapFewShot.compile", return_value=fake_compiled):
        result = await optimize_system_prompt(db_session, dataset_id, "anthropic", "claude-3-5-sonnet-20241022")

    assert result["exceeds_runtime_limit"] is True
