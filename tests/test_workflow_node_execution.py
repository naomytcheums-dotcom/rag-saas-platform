"""Phase 5, Étape 11 -- real, per-node execution tracing
(api/models/workflow_node_execution.py), the workflow-side equivalent
of AgentTrace. Tests the real trace rows `_advance`
(api/services/workflow_engine.py) writes for a successful path, a
failure path, and a human-block pause."""

import uuid

from sqlalchemy import select

from api.models.workflow import Workflow
from api.models.workflow_node_execution import WorkflowNodeExecution
from api.models.workflow_run import WorkflowRun, WorkflowRunStatus
from api.services.workflow_engine import execute_workflow_run, list_node_executions


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


async def test_execute_workflow_run_records_a_real_trace_per_node(db_session, monkeypatch):
    """Validation criterion: chaque nœud exécuté produit une vraie ligne de trace."""
    async def _fake_llm(config, context):
        return {config.get("output_key", "output"): "42"}

    monkeypatch.setattr("api.services.workflow_engine.execute_llm_block", _fake_llm)

    workflow = await _persist_workflow(
        db_session, nodes=[_node("start", "trigger"), _node("ask", "llm_call", {"output_key": "answer"})], edges=[_edge("start", "ask")],
    )
    run = await _persist_run(db_session, workflow)

    run = await execute_workflow_run(db_session, run)
    await db_session.commit()

    traces = await list_node_executions(db_session, run.id)
    assert [t.node_id for t in traces] == ["start", "ask"]
    assert traces[0].status == "completed"
    assert traces[1].node_type == "llm_call"
    assert traces[1].output == {"answer": "42"}
    assert traces[1].duration_ms is not None and traces[1].duration_ms >= 0


async def test_execute_workflow_run_records_a_real_failed_trace(db_session, monkeypatch):
    from api.services.workflow_blocks import WorkflowBlockError

    async def _boom(config, context):
        raise WorkflowBlockError("real, deliberate failure")

    monkeypatch.setattr("api.services.workflow_engine.execute_llm_block", _boom)

    workflow = await _persist_workflow(
        db_session, nodes=[_node("start", "trigger"), _node("ask", "llm_call")], edges=[_edge("start", "ask")],
    )
    run = await _persist_run(db_session, workflow)

    run = await execute_workflow_run(db_session, run)
    await db_session.commit()

    traces = await list_node_executions(db_session, run.id)
    assert traces[-1].status == "failed"
    assert "real, deliberate failure" in traces[-1].error


async def test_execute_workflow_run_records_a_waiting_human_trace(db_session):
    workflow = await _persist_workflow(
        db_session, nodes=[_node("start", "trigger"), _node("approve", "human", {"input_type": "confirm"})], edges=[_edge("start", "approve")],
    )
    run = await _persist_run(db_session, workflow)

    run = await execute_workflow_run(db_session, run)
    await db_session.commit()

    traces = await list_node_executions(db_session, run.id)
    assert traces[-1].status == "waiting_human"
    assert traces[-1].node_id == "approve"


async def test_node_executions_are_scoped_to_their_own_run(db_session, monkeypatch):
    """Validation criterion: pas de fuite de trace entre deux runs distincts."""
    async def _fake_llm(config, context):
        return {"answer": "ok"}

    monkeypatch.setattr("api.services.workflow_engine.execute_llm_block", _fake_llm)

    workflow = await _persist_workflow(
        db_session, nodes=[_node("start", "trigger"), _node("ask", "llm_call")], edges=[_edge("start", "ask")],
    )
    run_a = await _persist_run(db_session, workflow)
    run_b = await _persist_run(db_session, workflow)

    await execute_workflow_run(db_session, run_a)
    await execute_workflow_run(db_session, run_b)
    await db_session.commit()

    traces_a = await list_node_executions(db_session, run_a.id)
    traces_b = await list_node_executions(db_session, run_b.id)
    assert all(t.workflow_run_id == run_a.id for t in traces_a)
    assert all(t.workflow_run_id == run_b.id for t in traces_b)
    assert len(traces_a) == len(traces_b) == 2
