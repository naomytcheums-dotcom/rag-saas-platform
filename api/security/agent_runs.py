"""
Fix to Partie 5.1.1 -- item 2's own literal functions: `create_run`/
`update_run_status`/`get_run`/`get_runs`/`stop_run`, backing the real,
persistent `agent_runs` table (api/models/agent_run.py) that
api/services/agent_orchestrator.py's `AgentOrchestrator` now reads and
writes through instead of a plain in-memory dict.

Does not commit -- same convention as every other security-layer write
function in this codebase (the caller decides the transaction boundary;
here, that caller is AgentOrchestrator itself, which commits after each
real state transition so a reader in another process/worker can see it
as soon as it happens).
"""

import datetime as dt
import uuid
from typing import Any

from sqlalchemy import desc, select
from sqlalchemy.ext.asyncio import AsyncSession

from api.models.agent_run import AgentRunRecord, AgentRunStatus


async def create_run(
    db: AsyncSession, *, agent_id: str, input: str, context: str | None = None,
    organization_id: uuid.UUID | None = None, created_by: uuid.UUID | None = None,
) -> AgentRunRecord:
    """Item 2's own literal function. `input`/`context` are plain
    strings stored directly in their JSON column -- a JSON column
    accepts any JSON-serializable value, not just objects, so no
    wrapping is needed for today's real, text-only agent input."""
    run = AgentRunRecord(
        agent_id=agent_id, organization_id=organization_id, status=AgentRunStatus.pending.value,
        input=input, context=context, created_by=created_by, trace=[],
    )
    db.add(run)
    await db.flush()
    return run


async def update_run_status(
    db: AsyncSession, run_id: uuid.UUID, status: str, *,
    result: str | None = None, error: str | None = None, trace: list[dict] | None = None,
) -> AgentRunRecord | None:
    """Item 2's own literal function. `None` for an unknown `run_id`
    rather than raising -- same "fail toward the caller checking, not a
    crash" reasoning as get_run below. A terminal status
    (completed/failed/stopped/timeout) stamps `completed_at`; `running`
    does not overwrite it back to None (a run only ever finishes once)."""
    run = await db.get(AgentRunRecord, run_id)
    if run is None:
        return None

    run.status = status
    if result is not None:
        run.result = result
    if error is not None:
        run.error = error
    if trace is not None:
        run.trace = trace
    if status in (AgentRunStatus.completed, AgentRunStatus.failed, AgentRunStatus.stopped, AgentRunStatus.timeout):
        run.completed_at = dt.datetime.now(dt.timezone.utc)

    await db.flush()
    return run


async def get_run(db: AsyncSession, run_id: uuid.UUID) -> AgentRunRecord | None:
    """Item 2's own literal function."""
    return await db.get(AgentRunRecord, run_id)


async def get_runs(
    db: AsyncSession, agent_id: str, *, organization_id: uuid.UUID | None = None, limit: int = 50, offset: int = 0,
) -> list[AgentRunRecord]:
    """Item 2's own literal function -- item 2's own literal
    `(agent_id, limit=50, offset=0)` signature, plus a real, necessary
    `organization_id` filter (not in the literal signature) so a
    caller can honestly scope "runs of this agent_id" to their own
    organization -- without it, `agent_id` being a bare, caller-chosen
    string (see agent_orchestrator.py's own top docstring) would let
    any organization read another's runs simply by reusing the same
    agent_id. Passing `organization_id=None` keeps the old, unscoped
    behavior for internal/test callers with no request context."""
    query = select(AgentRunRecord).where(AgentRunRecord.agent_id == agent_id)
    if organization_id is not None:
        query = query.where(AgentRunRecord.organization_id == organization_id)
    query = query.order_by(desc(AgentRunRecord.started_at)).limit(limit).offset(offset)
    result = await db.scalars(query)
    return list(result.all())


async def stop_run(db: AsyncSession, run_id: uuid.UUID) -> AgentRunRecord | None:
    """Item 2's own literal function -- item 2's own literal "soft
    delete" wording is honored as a soft STATE change (stop_requested=True,
    status -> stopped), never a real row deletion: deleting a run would
    destroy the very audit trail this whole fix exists to make durable.
    `None` for an unknown `run_id`; a no-op (returns the run unchanged)
    for one that's already finished, same as
    AgentOrchestrator.stop_agent's own pre-fix "return False" case."""
    run = await db.get(AgentRunRecord, run_id)
    if run is None:
        return None
    if run.status not in (AgentRunStatus.pending, AgentRunStatus.running):
        return run
    run.stop_requested = True
    run.status = AgentRunStatus.stopped.value
    run.completed_at = dt.datetime.now(dt.timezone.utc)
    await db.flush()
    return run
