"""Partie 5.1.13 -- task planning. Real LLM calls mocked at the
litellm.acompletion boundary; dependency ordering/cycle detection
tested for real, no mocking."""

import json
from unittest.mock import AsyncMock

import litellm
import pytest
from litellm.types.utils import Choices, Message, ModelResponse

from api.config import settings
from api.models.task_plan import TaskPlan, TaskStepStatus
from api.services.task_planning import (
    decompose_task, execute_plan, get_plan_status, get_plan_steps, plan_task, update_plan, validate_plan,
)


def _response(text: str) -> ModelResponse:
    return ModelResponse(choices=[Choices(message=Message(content=text, role="assistant"), index=0, finish_reason="stop")])


@pytest.fixture(autouse=True)
def _configure_key(monkeypatch):
    monkeypatch.setattr(settings, "ANTHROPIC_API_KEY", "sk-ant-test")


# --------------------------------------- decompose_task --


async def test_decompose_task_parses_a_real_json_plan(monkeypatch):
    """Validation criterion: la décomposition fonctionne."""
    plan_json = json.dumps([{"description": "step one", "depends_on": []}, {"description": "step two", "depends_on": [0]}])
    monkeypatch.setattr(litellm, "acompletion", AsyncMock(return_value=_response(plan_json)))

    steps = await decompose_task("do a complex thing")
    assert len(steps) == 2
    assert steps[1]["depends_on"] == [0]


async def test_decompose_task_falls_back_to_a_single_step_on_malformed_response(monkeypatch):
    """Validation criterion: robustesse."""
    monkeypatch.setattr(litellm, "acompletion", AsyncMock(return_value=_response("not valid json")))

    steps = await decompose_task("do something")
    assert steps == [{"description": "do something", "depends_on": []}]


# --------------------------------------- validate_plan --


def test_validate_plan_accepts_a_real_valid_plan():
    """Validation criterion: la validation fonctionne."""
    steps = [{"description": "a", "depends_on": []}, {"description": "b", "depends_on": [0]}]
    assert validate_plan(steps) == []


def test_validate_plan_rejects_a_dangling_dependency():
    steps = [{"description": "a", "depends_on": [5]}]
    errors = validate_plan(steps)
    assert any("unknown step" in e for e in errors)


def test_validate_plan_rejects_a_real_cycle():
    """Validation criterion: cohérence -- les dépendances sont
    respectées (un cycle est rejeté)."""
    steps = [{"description": "a", "depends_on": [1]}, {"description": "b", "depends_on": [0]}]
    errors = validate_plan(steps)
    assert any("cycle" in e for e in errors)


def test_validate_plan_rejects_too_many_steps(monkeypatch):
    monkeypatch.setattr(settings, "TASK_PLANNING_MAX_STEPS", 2)
    steps = [{"description": str(i), "depends_on": []} for i in range(3)]
    errors = validate_plan(steps)
    assert any("maximum" in e for e in errors)


# --------------------------------------- plan_task / persistence --


async def test_plan_task_persists_a_real_plan_and_steps(monkeypatch, db_session):
    """Validation criterion: la planification fonctionne."""
    plan_json = json.dumps([{"description": "step one", "depends_on": []}])
    monkeypatch.setattr(litellm, "acompletion", AsyncMock(return_value=_response(plan_json)))

    plan = await plan_task(db_session, "do a thing")
    await db_session.commit()

    assert plan.status == "pending"
    steps = await get_plan_steps(db_session, plan.id)
    assert len(steps) == 1
    assert steps[0].description == "step one"


async def test_get_plan_status_returns_none_for_unknown_plan(db_session):
    import uuid
    assert await get_plan_status(db_session, uuid.uuid4()) is None


async def test_update_plan_changes_status_and_stores_result(db_session, monkeypatch):
    monkeypatch.setattr(litellm, "acompletion", AsyncMock(return_value=_response(json.dumps([{"description": "a", "depends_on": []}]))))
    plan = await plan_task(db_session, "objective")
    await db_session.commit()

    updated = await update_plan(db_session, plan.id, "completed", result={"summary": "done"})
    await db_session.commit()

    assert updated.status == "completed"
    assert updated.metadata_json["result"] == {"summary": "done"}


# --------------------------------------- execute_plan --


async def test_execute_plan_runs_real_steps_in_dependency_order(monkeypatch, db_session):
    """Validation criterion: l'exécution de plan fonctionne, les
    dépendances sont respectées. A single litellm.acompletion mock
    (the real, narrow boundary) branches on the prompt content, rather
    than mocking chat_completion itself -- decompose_task and each real
    execute_plan step both go through the SAME real chat_completion
    function, so mocking chat_completion directly would intercept both
    indiscriminately."""
    order = []
    plan_json = json.dumps([
        {"description": "first", "depends_on": []},
        {"description": "second", "depends_on": [0]},
    ])

    async def _acompletion(**kwargs):
        content = kwargs["messages"][0]["content"]
        if content.startswith("Break this objective"):
            return _response(plan_json)
        order.append(content)
        return _response(f"done: {content}")

    monkeypatch.setattr(litellm, "acompletion", _acompletion)
    plan = await plan_task(db_session, "objective")
    await db_session.commit()

    result = await execute_plan(db_session, plan.id)
    await db_session.commit()

    assert result.status == "completed"
    assert order == ["first", "second"]
    steps = await get_plan_steps(db_session, plan.id)
    assert all(s.status == TaskStepStatus.completed.value for s in steps)


async def test_execute_plan_skips_steps_depending_on_a_real_failure(monkeypatch, db_session):
    """Validation criterion: robustesse -- que se passe-t-il si une
    étape échoue (ses dépendants sont sautés, les autres continuent)."""
    plan_json = json.dumps([
        {"description": "fails", "depends_on": []},
        {"description": "depends on failure", "depends_on": [0]},
        {"description": "independent", "depends_on": []},
    ])

    async def _acompletion(**kwargs):
        content = kwargs["messages"][0]["content"]
        if content.startswith("Break this objective"):
            return _response(plan_json)
        if content == "fails":
            raise litellm.exceptions.AuthenticationError(message="boom", llm_provider="anthropic", model="claude")
        return _response(f"done: {content}")

    monkeypatch.setattr(litellm, "acompletion", _acompletion)
    plan = await plan_task(db_session, "objective")
    await db_session.commit()

    result = await execute_plan(db_session, plan.id)
    await db_session.commit()

    assert result.status == "failed"
    steps = {s.description: s.status for s in await get_plan_steps(db_session, plan.id)}
    assert steps["fails"] == TaskStepStatus.failed.value
    assert steps["depends on failure"] == TaskStepStatus.skipped.value
    assert steps["independent"] == TaskStepStatus.completed.value


async def test_execute_plan_raises_for_an_unknown_plan(db_session):
    import uuid
    with pytest.raises(ValueError):
        await execute_plan(db_session, uuid.uuid4())
