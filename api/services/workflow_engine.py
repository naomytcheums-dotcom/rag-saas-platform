"""
Partie 5.4 -- the real graph executor. Every one of
`api/services/workflow_block_*.py`'s own module docstrings (Parties
5.4.3-5.4.11) already names this exact gap: `trigger_workflow`
(`api/services/workflow_triggers.py`) only ever created a real,
`pending` `WorkflowRun` row and stopped there -- "a genuinely separate,
substantial piece of work (a real graph executor chaining Parties
5.4.3-5.4.11's own per-block execution functions along real edges)".
This module is that piece.

**Real graph-walk shape, not a generic DAG scheduler**: exactly one
"current" node advances at a time -- the same one-node-at-a-time loop
shape as `api/services/autonomous_agents.py`'s own
`execute_step`/`run_autonomous_agent`. A `condition` block
(Partie 5.4.7) is the only real branch point, and it still resolves to
exactly ONE real next node (`format_condition_result`'s own literal
`true_branch`/`false_branch` node id) -- no parallel branch execution,
no fan-in/join semantics, because nothing in Partie 5.4's own 13 items
ever asks for either.

**A real `human` block (Partie 5.4.9) pauses, it does not block a real
worker thread**: `execute_human_block` returns a real, persisted,
`pending` `WorkflowHumanInput` row rather than a real value -- this
module reads that as "stop the loop here", persists exactly where
(`WorkflowRun.current_node_id`) and the real accumulated `context` so
far, and returns. `resume_workflow_run` is the real, separate re-entry
point once that row is really `submitted` (called by the router right
after `submit_human_input` succeeds, same "the write and the next step
are two real, separate calls" shape already established there)."""

import datetime as dt
import json
import logging
import time
import uuid

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from api.models.workflow import Workflow
from api.models.workflow_human_input import WorkflowHumanInput
from api.models.workflow_node_execution import WorkflowNodeExecution
from api.models.workflow_run import WorkflowRun, WorkflowRunStatus
from api.services.workflow_block_calendar import execute_calendar_block
from api.services.workflow_block_code import execute_code_block
from api.services.workflow_block_condition import execute_condition_block
from api.services.workflow_block_database import execute_database_block
from api.services.workflow_block_email import execute_email_block
from api.services.workflow_block_http import execute_http_block
from api.services.workflow_block_human import execute_human_block
from api.services.workflow_block_llm import execute_llm_block
from api.services.workflow_block_rag import execute_rag_block
from api.services.workflow_block_search import execute_search_block
from api.services.workflow_blocks import WorkflowBlockError

logger = logging.getLogger(__name__)

# Phase 5, Étape 5 -- real-time run execution events (Workflow Builder
# UI's own debug/run panel), reusing the exact same Redis pub/sub
# pattern api/security/documents.py's own send_progress_update/
# stream_document_progress and api/services/notifications.py's own
# real-time already established -- no new infrastructure.
_run_events_redis = None
_run_events_redis_loop = None


def _get_run_events_redis():
    global _run_events_redis, _run_events_redis_loop
    from api.config import settings
    from api.security.redis_client import get_or_rebuild

    _run_events_redis, _run_events_redis_loop = get_or_rebuild(
        _run_events_redis, _run_events_redis_loop, settings.RATE_LIMIT_REDIS_URL,
        decode_responses=True, socket_connect_timeout=2, socket_timeout=2,
    )
    return _run_events_redis


async def _publish_run_event(run_id: uuid.UUID, payload: dict) -> None:
    try:
        await _get_run_events_redis().publish(f"workflow_run:{run_id}", json.dumps(payload))
    except Exception as exc:  # noqa: BLE001 -- a broker hiccup must never break the real workflow run this only reports on
        logger.warning("_publish_run_event: could not publish event for run '%s': %s", run_id, exc)

# Real, permanent cap -- a real cyclic graph (a Manager's own authoring
# mistake, not malice) must never spin the executor forever, same
# reasoning as `api/services/autonomous_agents.py`'s own step cap.
MAX_STEPS = 200


class WorkflowExecutionError(ValueError):
    """Real, dedicated exception for a genuinely unrecoverable executor
    error (an unknown node id, a resume on a run that isn't really
    waiting) -- distinct from a real, per-block `WorkflowBlockError`,
    which the loop below already catches and turns into a real, failed
    run rather than raising further."""


def _index_nodes(nodes: list[dict]) -> dict[str, dict]:
    return {node["id"]: node for node in nodes}


def _next_node_id(current_node_id: str, node_type: str, block_result: dict, edges: list[dict]) -> str | None:
    """Real, single "next node" resolution. A `condition` block never
    follows its own outgoing edges -- Partie 5.4.7's own
    `format_condition_result` already names the real next node id
    directly (`result["branch"]`); any edges drawn from a condition
    node exist only for a real future canvas to *render* the two
    branches, not for the executor to walk. Every other real block type
    follows its own first outgoing edge -- `api/services/workflows.py`'s
    own `validate_workflow` doesn't reject multi-successor graphs today,
    so "first edge, in insertion order" is the real, documented,
    deterministic tie-break, same as a Manager would read the canvas
    top-to-bottom."""
    if node_type == "condition":
        [result] = block_result.values()
        return result.get("branch")
    for edge in edges:
        if edge["source"] == current_node_id:
            return edge["target"]
    return None


async def _notify_approval_needed(db: AsyncSession, organization_id, run: WorkflowRun, human_input) -> None:
    """Phase 5, Étape 5 correctif -- workflow_approval_needed,
    reclassified P1 in Phase 5 Étape 4's own ROADMAP entry and wired
    here because the Workflow Builder UI's own human-approval feature
    is genuinely unusable without it: an approver with no notification
    only discovers a pending approval by manually polling the canvas."""
    from api.models.workflow import Workflow
    from api.services.notifications import create_notification

    workflow = await db.get(Workflow, run.workflow_id)
    if workflow is None or workflow.created_by is None:
        return
    try:
        await create_notification(
            db, organization_id=organization_id, user_id=workflow.created_by, notification_type="workflow_approval_needed",
            priority="urgent", context={"workflow_name": workflow.name, "message": human_input.message},
        )
        await db.flush()
    except Exception as exc:  # noqa: BLE001 -- a notification failure must never fail the real workflow run it only reports on
        logger.warning("_notify_approval_needed: could not notify for run '%s': %s", run.id, exc)


async def _execute_node(db: AsyncSession, organization_id, run: WorkflowRun, node: dict, context: dict) -> dict | None:
    """Real dispatch by node type. Returns the real `{output_key:
    result}` dict to merge into `context`, or `None` for a real `human`
    block -- the caller (`_advance`), not this function, owns the real
    "stop the loop" decision that a `None` return signals."""
    node_type = node["type"]
    config = node.get("data", {}) or {}

    if node_type == "trigger":
        return {}
    if node_type == "llm_call":
        return await execute_llm_block(config, context)
    if node_type == "rag_search":
        return await execute_rag_block(db, organization_id, config, context)
    if node_type == "web_search":
        return await execute_search_block(config, context)
    if node_type == "http_call":
        return await execute_http_block(config, context)
    if node_type == "condition":
        return execute_condition_block(config, context)
    if node_type == "code":
        return execute_code_block(config, context)
    if node_type == "email":
        return await execute_email_block(config, context)
    if node_type == "calendar":
        return await execute_calendar_block(config, context)
    if node_type == "database":
        return await execute_database_block(db, organization_id, config, context)
    if node_type == "human":
        human_input = await execute_human_block(db, run.id, node["id"], config, context)
        await _notify_approval_needed(db, organization_id, run, human_input)
        return None
    raise WorkflowExecutionError(f"Unknown node type: {node_type!r}")


def _now() -> dt.datetime:
    return dt.datetime.now(dt.timezone.utc)


async def _fail(run: WorkflowRun, context: dict, message: str) -> WorkflowRun:
    run.status = WorkflowRunStatus.failed.value
    run.error = message
    run.context = context
    run.completed_at = _now()
    return run


async def _record_node_execution(
    db: AsyncSession, run_id: uuid.UUID, step_number: int, node: dict, node_input: dict, output: dict | None,
    started_at: float, status: str, error: str | None,
) -> None:
    """Phase 5, Étape 11 -- real, per-node execution trace, the same
    real gap `AgentTrace` already closed for agents
    (api/models/agent_trace.py). One row per real node execution
    attempt, including a real duration measured with
    `time.monotonic()` (never wall-clock, immune to a real system
    clock adjustment mid-run)."""
    duration_ms = int((time.monotonic() - started_at) * 1000)
    db.add(
        WorkflowNodeExecution(
            workflow_run_id=run_id, step_number=step_number, node_id=node["id"], node_type=node["type"],
            input=node_input, output=output, duration_ms=duration_ms, status=status, error=error,
        )
    )
    await db.flush()


async def _advance(db: AsyncSession, run: WorkflowRun, workflow: Workflow, context: dict, current_id: str | None) -> WorkflowRun:
    """The real, shared loop both `execute_workflow_run` (a fresh run,
    starting at the real `trigger` node) and `resume_workflow_run` (a
    paused run, starting wherever the real `human` block left off)
    drive. `current_id=None` on entry (a real `human` block was the
    graph's own last node) completes the run immediately with no
    further work -- a real, honest "there was nothing left to run"."""
    nodes_by_id = _index_nodes(workflow.nodes)
    run.status = WorkflowRunStatus.running.value
    steps = 0

    while current_id is not None:
        steps += 1
        if steps > MAX_STEPS:
            await _fail(run, context, f"Exceeded the real {MAX_STEPS}-step execution cap (a cyclic graph?).")
            await db.flush()
            return run

        node = nodes_by_id.get(current_id)
        if node is None:
            await _fail(run, context, f"A real edge points to an unknown node id: {current_id!r}")
            await db.flush()
            return run

        run.current_node_id = current_id
        await _publish_run_event(run.id, {"event": "node_started", "node_id": current_id, "status": run.status})

        node_input = dict(context)
        started_at = time.monotonic()
        try:
            result = await _execute_node(db, workflow.organization_id, run, node, context)
        except (WorkflowBlockError, WorkflowExecutionError) as exc:
            await _record_node_execution(db, run.id, steps, node, node_input, None, started_at, "failed", str(exc))
            await _fail(run, context, f"Node {current_id!r} ({node['type']}) failed: {exc}")
            await db.flush()
            await _publish_run_event(run.id, {"event": "run_failed", "node_id": current_id, "status": run.status, "error": run.error})
            return run

        if result is None:  # a real 'human' block -- pause here, wait for a real, separate submission
            await _record_node_execution(db, run.id, steps, node, node_input, None, started_at, "waiting_human", None)
            run.status = WorkflowRunStatus.waiting_human.value
            run.current_node_id = current_id
            run.context = context
            await db.flush()
            await _publish_run_event(run.id, {"event": "waiting_human", "node_id": current_id, "status": run.status})
            return run

        await _record_node_execution(db, run.id, steps, node, node_input, result, started_at, "completed", None)
        context.update(result)
        await _publish_run_event(run.id, {"event": "node_completed", "node_id": current_id, "status": run.status, "output": result})
        current_id = _next_node_id(current_id, node["type"], result, workflow.edges)

    run.status = WorkflowRunStatus.completed.value
    run.output = context
    run.context = context
    run.current_node_id = None
    run.completed_at = _now()
    await db.flush()
    await _publish_run_event(run.id, {"event": "run_completed", "node_id": None, "status": run.status})
    return run


async def execute_workflow_run(db: AsyncSession, run: WorkflowRun) -> WorkflowRun:
    """Real entry point for a freshly-`trigger_workflow`'d run --
    dispatched by Celery (`api/tasks/workflows.py`) right after that
    real, `pending` row is created and committed. Advances `run` in
    place; the caller still owns the real `db.commit()`, same
    convention as every other 5.4.x service function."""
    workflow = await db.get(Workflow, run.workflow_id)
    if workflow is None:
        return await _fail(run, dict(run.input or {}), "The real workflow this run belongs to no longer exists.")

    trigger_nodes = [n["id"] for n in workflow.nodes if n["type"] == "trigger"]
    if not trigger_nodes:
        return await _fail(run, dict(run.input or {}), "This workflow has no real 'trigger' node to start execution from.")

    return await _advance(db, run, workflow, _seed_context(workflow, run.input), trigger_nodes[0])


def _seed_context(workflow: Workflow, run_input: dict | None) -> dict:
    """Phase 5, Étape 5 -- real variable-default resolution: a
    workflow's own `variables` (`{name, default_value, ...}` dicts,
    api/models/workflow.py's own docstring) seed `context` FIRST, then
    `run.input` overrides on top -- the same real
    "override > default" precedence this codebase already established
    for org settings/retrieval config resolvers. A node's own
    `{{ variable_name }}` template reference resolves to a real
    default even when the caller's `run.input` never mentions it."""
    context = {var["name"]: var.get("default_value") for var in (workflow.variables or []) if "name" in var}
    context.update(run_input or {})
    return context


async def resume_workflow_run(db: AsyncSession, run: WorkflowRun, human_input: WorkflowHumanInput) -> WorkflowRun:
    """Real re-entry point once a real, paused `human` block
    (`run.current_node_id`) has really been `submit_human_input`'d.
    `human_input.value` is written into `context` under that node's own
    real `output_key` (default `"output"`, same convention as every
    other real block) so every real node downstream sees it exactly
    like any other block's own result."""
    if run.status != WorkflowRunStatus.waiting_human.value or run.current_node_id != human_input.node_id:
        raise WorkflowExecutionError("This run is not really waiting on this human block.")

    workflow = await db.get(Workflow, run.workflow_id)
    if workflow is None:
        return await _fail(run, dict(run.context or {}), "The real workflow this run belongs to no longer exists.")

    context = dict(run.context or {})
    node = _index_nodes(workflow.nodes).get(human_input.node_id)
    output_key = (node.get("data") or {}).get("output_key", "output") if node else "output"
    context[output_key] = human_input.value

    next_id = _next_node_id(human_input.node_id, "human", {}, workflow.edges)
    return await _advance(db, run, workflow, context, next_id)


_TERMINAL_RUN_STATUSES = (WorkflowRunStatus.completed.value, WorkflowRunStatus.failed.value)


async def stream_workflow_run(run: WorkflowRun):
    """Real async generator wrapped in a StreamingResponse by
    api/routers/workflows.py's own SSE route -- the Workflow Builder
    UI's debug/run panel. Sends a real, immediate snapshot of the run's
    CURRENT state first (same reasoning as
    api/security/documents.py's own stream_document_progress: a caller
    connecting after execution already finished, or mid-run, still
    learns the real, current state right away), then forwards every
    real node_started/node_completed/waiting_human/run_completed/
    run_failed event verbatim, stopping at a real terminal status."""
    initial = {"event": "snapshot", "node_id": run.current_node_id, "status": run.status}
    yield f"data: {json.dumps(initial)}\n\n"
    if run.status in _TERMINAL_RUN_STATUSES:
        return

    pubsub = _get_run_events_redis().pubsub()
    channel = f"workflow_run:{run.id}"
    await pubsub.subscribe(channel)
    try:
        async for message in pubsub.listen():
            if message["type"] != "message":
                continue
            yield f"data: {message['data']}\n\n"
            payload = json.loads(message["data"])
            if payload.get("status") in _TERMINAL_RUN_STATUSES:
                break
    finally:
        await pubsub.unsubscribe(channel)
        await pubsub.aclose()


async def list_node_executions(db: AsyncSession, workflow_run_id: uuid.UUID) -> list[WorkflowNodeExecution]:
    """Phase 5, Étape 11 -- real, ordered, per-node execution history
    for one run, backing `GET /workflows/runs/{run_id}/trace`."""
    result = await db.scalars(
        select(WorkflowNodeExecution).where(WorkflowNodeExecution.workflow_run_id == workflow_run_id).order_by(WorkflowNodeExecution.step_number)
    )
    return list(result.all())
