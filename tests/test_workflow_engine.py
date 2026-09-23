"""Partie 5.4 -- the real graph executor
(`api/services/workflow_engine.py`). Every real per-block
`execute_*_block` function is already covered by its own dedicated test
module (`tests/test_workflow_block_*.py`); these tests instead cover
what those modules explicitly leave untested: walking real edges
between real nodes, `condition`'s own real branch-by-node-id, a real
`human` block's own real pause/resume, and the executor's own real
failure modes (dangling edge, no trigger, unknown node type, a cyclic
graph)."""

import uuid

import pytest
from sqlalchemy import select

from api.models.workflow import Workflow
from api.models.workflow_human_input import HumanInputStatus, WorkflowHumanInput
from api.models.workflow_run import WorkflowRun, WorkflowRunStatus
from api.services.workflow_block_human import submit_human_input
from api.services.workflow_blocks import WorkflowBlockError
from api.services.workflow_engine import (
    WorkflowExecutionError, execute_workflow_run, resume_workflow_run,
)


def _node(node_id: str, node_type: str, data: dict | None = None) -> dict:
    return {"id": node_id, "type": node_type, "position": {"x": 0, "y": 0}, "data": data or {}}


def _edge(source: str, target: str) -> dict:
    return {"id": str(uuid.uuid4()), "source": source, "target": target}


async def _persist_workflow(db_session, nodes: list[dict], edges: list[dict]) -> Workflow:
    workflow = Workflow(organization_id=uuid.uuid4(), name="Test workflow", nodes=nodes, edges=edges)
    db_session.add(workflow)
    await db_session.commit()
    await db_session.refresh(workflow)
    return workflow


async def _persist_run(db_session, workflow: Workflow, input: dict | None = None) -> WorkflowRun:
    run = WorkflowRun(workflow_id=workflow.id, status=WorkflowRunStatus.pending.value, input=input or {})
    db_session.add(run)
    await db_session.commit()
    await db_session.refresh(run)
    return run


# --------------------------------------- linear execution --


async def test_execute_workflow_run_walks_a_real_linear_graph(db_session, monkeypatch):
    """Validation criterion: le moteur exécute réellement un graphe simple de bout en bout."""
    async def _fake_llm(config, context):
        return {config.get("output_key", "output"): f"answer for {context.get('question')}"}

    monkeypatch.setattr("api.services.workflow_engine.execute_llm_block", _fake_llm)

    workflow = await _persist_workflow(
        db_session,
        nodes=[_node("start", "trigger"), _node("ask", "llm_call", {"user_prompt": "{{question}}", "output_key": "answer"})],
        edges=[_edge("start", "ask")],
    )
    run = await _persist_run(db_session, workflow, input={"question": "life"})

    run = await execute_workflow_run(db_session, run)
    await db_session.commit()

    assert run.status == WorkflowRunStatus.completed.value
    assert run.output == {"question": "life", "answer": "answer for life"}
    assert run.completed_at is not None


async def test_execute_workflow_run_fails_when_no_trigger_node(db_session):
    """Validation criterion: robustesse -- graphe sans point de départ."""
    workflow = await _persist_workflow(db_session, nodes=[_node("a", "llm_call")], edges=[])
    run = await _persist_run(db_session, workflow)

    run = await execute_workflow_run(db_session, run)

    assert run.status == WorkflowRunStatus.failed.value
    assert "trigger" in run.error


async def test_execute_workflow_run_fails_on_a_dangling_edge(db_session):
    """Validation criterion: robustesse -- une arête pointe vers un noeud inexistant."""
    workflow = await _persist_workflow(
        db_session, nodes=[_node("start", "trigger")], edges=[_edge("start", "ghost")],
    )
    run = await _persist_run(db_session, workflow)

    run = await execute_workflow_run(db_session, run)

    assert run.status == WorkflowRunStatus.failed.value
    assert "ghost" in run.error


async def test_execute_workflow_run_fails_on_an_unknown_node_type(db_session):
    """Validation criterion: robustesse -- type de bloc inconnu (contourne validate_workflow)."""
    workflow = await _persist_workflow(
        db_session, nodes=[_node("start", "trigger"), _node("weird", "not-a-real-block")],
        edges=[_edge("start", "weird")],
    )
    run = await _persist_run(db_session, workflow)

    run = await execute_workflow_run(db_session, run)

    assert run.status == WorkflowRunStatus.failed.value
    assert "not-a-real-block" in run.error


async def test_execute_workflow_run_turns_a_real_block_error_into_a_failed_run(db_session, monkeypatch):
    """Validation criterion: robustesse -- un vrai échec de bloc (ex. LLM) ne fait pas planter le worker."""
    async def _raise(config, context):
        raise WorkflowBlockError("llm_call block requires a real, non-empty 'user_prompt'")

    monkeypatch.setattr("api.services.workflow_engine.execute_llm_block", _raise)

    workflow = await _persist_workflow(
        db_session, nodes=[_node("start", "trigger"), _node("ask", "llm_call")], edges=[_edge("start", "ask")],
    )
    run = await _persist_run(db_session, workflow)

    run = await execute_workflow_run(db_session, run)

    assert run.status == WorkflowRunStatus.failed.value
    assert "ask" in run.error and "user_prompt" in run.error


async def test_execute_workflow_run_stops_at_a_real_step_cap_on_a_cyclic_graph(db_session, monkeypatch):
    """Validation criterion: robustesse -- un graphe cyclique ne boucle pas indéfiniment."""
    async def _fake_llm(config, context):
        return {"output": "x"}

    monkeypatch.setattr("api.services.workflow_engine.MAX_STEPS", 5)
    monkeypatch.setattr("api.services.workflow_engine.execute_llm_block", _fake_llm)

    workflow = await _persist_workflow(
        db_session,
        nodes=[_node("start", "trigger"), _node("a", "llm_call"), _node("b", "llm_call")],
        edges=[_edge("start", "a"), _edge("a", "b"), _edge("b", "a")],
    )
    run = await _persist_run(db_session, workflow)

    run = await execute_workflow_run(db_session, run)

    assert run.status == WorkflowRunStatus.failed.value
    assert "step" in run.error.lower()


# --------------------------------------- condition branching --


async def test_execute_workflow_run_follows_the_true_branch(db_session):
    """Validation criterion: le bloc condition choisit réellement la bonne branche."""
    workflow = await _persist_workflow(
        db_session,
        nodes=[
            _node("start", "trigger"),
            _node("check", "condition", {"condition": "score > 5", "true_branch": "high", "false_branch": "low"}),
            _node("high", "code", {"code": "'HIGH'"}),
            _node("low", "code", {"code": "'LOW'"}),
        ],
        edges=[_edge("start", "check")],
    )
    run = await _persist_run(db_session, workflow, input={"score": 9})

    run = await execute_workflow_run(db_session, run)

    assert run.status == WorkflowRunStatus.completed.value
    assert run.output["output"]["result"] == "HIGH"


async def test_execute_workflow_run_follows_the_false_branch(db_session):
    workflow = await _persist_workflow(
        db_session,
        nodes=[
            _node("start", "trigger"),
            _node("check", "condition", {"condition": "score > 5", "true_branch": "high", "false_branch": "low"}),
            _node("high", "code", {"code": "'HIGH'"}),
            _node("low", "code", {"code": "'LOW'"}),
        ],
        edges=[_edge("start", "check")],
    )
    run = await _persist_run(db_session, workflow, input={"score": 1})

    run = await execute_workflow_run(db_session, run)

    assert run.status == WorkflowRunStatus.completed.value
    assert run.output["output"]["result"] == "LOW"


# --------------------------------------- human pause / resume --


async def test_execute_workflow_run_pauses_on_a_human_block(db_session):
    """Validation criterion: le bloc human met réellement le run en pause."""
    workflow = await _persist_workflow(
        db_session,
        nodes=[_node("start", "trigger"), _node("approve", "human", {"message": "OK?", "input_type": "confirm"})],
        edges=[_edge("start", "approve")],
    )
    run = await _persist_run(db_session, workflow)

    run = await execute_workflow_run(db_session, run)
    await db_session.commit()

    assert run.status == WorkflowRunStatus.waiting_human.value
    assert run.current_node_id == "approve"

    pending = (await db_session.scalars(
        select(WorkflowHumanInput).where(WorkflowHumanInput.workflow_run_id == run.id)
    )).one()
    assert pending.status == HumanInputStatus.pending.value
    assert pending.node_id == "approve"


async def test_resume_workflow_run_continues_after_a_real_submission(db_session):
    """Validation criterion: la reprise après une entrée humaine fonctionne et transmet la valeur."""
    workflow = await _persist_workflow(
        db_session,
        nodes=[
            _node("start", "trigger"),
            _node("approve", "human", {"message": "OK?", "input_type": "confirm", "output_key": "approved"}),
            _node("after", "code", {"code": "'done: ' + str(approved)"}),
        ],
        edges=[_edge("start", "approve"), _edge("approve", "after")],
    )
    run = await _persist_run(db_session, workflow)
    run = await execute_workflow_run(db_session, run)
    await db_session.commit()
    assert run.status == WorkflowRunStatus.waiting_human.value

    pending = (await db_session.scalars(
        select(WorkflowHumanInput).where(WorkflowHumanInput.workflow_run_id == run.id)
    )).one()
    submitted = await submit_human_input(db_session, pending.id, None, True)
    await db_session.commit()

    run = await resume_workflow_run(db_session, run, submitted)
    await db_session.commit()

    assert run.status == WorkflowRunStatus.completed.value
    assert run.output["approved"] is True
    assert run.output["output"]["result"] == "done: True"


async def test_resume_workflow_run_rejects_a_run_that_is_not_really_waiting(db_session):
    """Validation criterion: robustesse -- pas de reprise sur un run déjà terminé."""
    workflow = await _persist_workflow(db_session, nodes=[_node("start", "trigger")], edges=[])
    run = await _persist_run(db_session, workflow)
    run = await execute_workflow_run(db_session, run)
    await db_session.commit()
    assert run.status == WorkflowRunStatus.completed.value

    fake_input = WorkflowHumanInput(workflow_run_id=run.id, node_id="approve", message="x", value=True)

    with pytest.raises(WorkflowExecutionError):
        await resume_workflow_run(db_session, run, fake_input)


async def test_execute_workflow_run_completes_immediately_when_human_is_the_last_node(db_session):
    """Validation criterion: robustesse -- un bloc human sans suite termine le run après reprise."""
    workflow = await _persist_workflow(
        db_session, nodes=[_node("start", "trigger"), _node("approve", "human", {"message": "OK?"})],
        edges=[_edge("start", "approve")],
    )
    run = await _persist_run(db_session, workflow)
    run = await execute_workflow_run(db_session, run)
    await db_session.commit()

    pending = (await db_session.scalars(
        select(WorkflowHumanInput).where(WorkflowHumanInput.workflow_run_id == run.id)
    )).one()
    submitted = await submit_human_input(db_session, pending.id, None, "yes")
    await db_session.commit()

    run = await resume_workflow_run(db_session, run, submitted)

    assert run.status == WorkflowRunStatus.completed.value
    assert run.current_node_id is None


# --------------------------------------- Phase 5, Étape 5 correctif: workflow_approval_needed --

async def test_human_block_notifies_the_workflows_creator(db_session):
    """Validation criterion: workflow_approval_needed (P1, reclassified
    in Phase 5 Étape 4) is genuinely wired -- a real org owner/creator
    gets a real, persisted in-app notification the moment a run pauses
    on a human block, not just a theoretical API they'd have to poll."""
    from unittest.mock import AsyncMock, patch

    from api.models.organization import Organization, OrganizationMember, OrganizationRole
    from api.models.user import User
    from api.security.hashing import hash_password
    from api.services.notifications import list_notifications

    user = User(email="workflowcreator@example.com", hashed_password=hash_password("correct-horse-battery-staple"))
    org = Organization(name="Workflow Notif Org", slug=f"wf-notif-org-{uuid.uuid4().hex[:8]}")
    db_session.add_all([user, org])
    await db_session.flush()
    db_session.add(OrganizationMember(organization_id=org.id, user_id=user.id, role=OrganizationRole.owner))
    await db_session.commit()

    workflow = Workflow(
        organization_id=org.id, name="Needs Approval", created_by=user.id,
        nodes=[_node("start", "trigger"), _node("approve", "human", {"message": "Please review", "input_type": "confirm"})],
        edges=[_edge("start", "approve")],
    )
    db_session.add(workflow)
    await db_session.commit()
    run = await _persist_run(db_session, workflow)

    with patch("api.services.notifications._publish_realtime", new_callable=AsyncMock), patch("api.tasks.notifications.send_notification_email_task.delay"):
        run = await execute_workflow_run(db_session, run)
        await db_session.commit()

    assert run.status == WorkflowRunStatus.waiting_human.value
    notifications = await list_notifications(db_session, user.id)
    assert any(n.type == "workflow_approval_needed" for n in notifications)
    approval_notification = next(n for n in notifications if n.type == "workflow_approval_needed")
    assert "Please review" in approval_notification.body
    assert approval_notification.priority == "urgent"
