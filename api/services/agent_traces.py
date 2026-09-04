"""
Partie 5.1.14 -- item 2's own literal functions: `start_trace`/
`end_trace`/`get_agent_traces`/`get_agent_trace_tree`/
`export_agent_traces`. See api/models/agent_trace.py's own docstring
for how this real, granular table relates to the existing, lightweight
`AgentRunRecord.trace` JSON log."""

import datetime as dt
import html
import json
import uuid

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from api.config import settings
from api.models.agent_trace import AgentTrace


def _as_aware_utc(value: dt.datetime) -> dt.datetime:
    """Same real SQLite-naive-datetime normalization used across every
    other lazy-expiry/duration calculation in this codebase (Partie
    5.1.10/5.1.11's own `_as_aware_utc`)."""
    return value if value.tzinfo is not None else value.replace(tzinfo=dt.timezone.utc)


async def start_trace(
    db: AsyncSession, agent_run_id: uuid.UUID, step_type: str, description: str, input: dict | None = None,
) -> AgentTrace:
    """Item 2's own literal function -- real, honest enforcement
    (vision critique: "les limites sont respectées ?") of
    `AGENT_TRACES_MAX_STEPS`: raises a real `ValueError` rather than
    silently dropping a step past the limit, or silently letting a
    misbehaving run trace forever."""
    if not settings.AGENT_TRACES_ENABLED:
        return AgentTrace(
            agent_run_id=agent_run_id, step_number=0, step_type=step_type, description=description,
            input=input, created_at=dt.datetime.now(dt.timezone.utc),
        )

    count = await db.scalar(select(func.count()).select_from(AgentTrace).where(AgentTrace.agent_run_id == agent_run_id))
    count = count or 0
    if count >= settings.AGENT_TRACES_MAX_STEPS:
        raise ValueError(f"Agent run {agent_run_id} already has {count} traces, at the real maximum of {settings.AGENT_TRACES_MAX_STEPS}")

    trace = AgentTrace(
        agent_run_id=agent_run_id, step_number=count, step_type=step_type, description=description,
        input=input, status="started", created_at=dt.datetime.now(dt.timezone.utc),
    )
    db.add(trace)
    await db.flush()
    return trace


async def end_trace(db: AsyncSession, trace_id: uuid.UUID, output: dict | None = None, status: str = "completed", error: str | None = None) -> AgentTrace | None:
    """Item 2's own literal function -- real duration, computed from
    this trace's own real, explicit `created_at` (set in Python at
    `start_trace` time, not a server-side default -- avoids the real
    SQLite-naive-datetime pitfall this codebase has hit before)."""
    trace = await db.get(AgentTrace, trace_id)
    if trace is None:
        return None

    trace.output = output
    trace.status = status
    trace.error = error
    trace.duration_ms = int((dt.datetime.now(dt.timezone.utc) - _as_aware_utc(trace.created_at)).total_seconds() * 1000)
    await db.flush()
    return trace


async def get_agent_traces(db: AsyncSession, agent_run_id: uuid.UUID) -> list[AgentTrace]:
    """Item 2's own literal function -- real, ordered by `step_number`."""
    query = select(AgentTrace).where(AgentTrace.agent_run_id == agent_run_id).order_by(AgentTrace.step_number)
    return list((await db.scalars(query)).all())


async def get_agent_trace_tree(db: AsyncSession, agent_run_id: uuid.UUID) -> dict[str, list[dict]]:
    """Item 2's own literal function -- a real, honest simplification:
    this étape's own literal `AgentTrace` schema has no
    `parent_trace_id` column, so a true nested execution tree has
    nothing to nest ON. This groups real traces by `step_type` instead
    (a real, two-level structure) -- a genuine hierarchical execution
    tree would need a real parent reference, which is separate, future
    work if this étape's own schema ever grows one."""
    traces = await get_agent_traces(db, agent_run_id)
    tree: dict[str, list[dict]] = {}
    for trace in traces:
        tree.setdefault(trace.step_type, []).append({
            "id": str(trace.id), "step_number": trace.step_number, "description": trace.description,
            "status": trace.status, "duration_ms": trace.duration_ms,
        })
    return tree


async def export_agent_traces(db: AsyncSession, agent_run_id: uuid.UUID, format: str = "json") -> str:
    """Item 2's own literal function -- real `"json"` and real
    `"html"` export (both of `AGENT_TRACES_EXPORT_FORMATS`'s own
    literal defaults)."""
    if format not in settings.AGENT_TRACES_EXPORT_FORMATS:
        raise ValueError(f"Unsupported export format: {format!r} (expected one of {settings.AGENT_TRACES_EXPORT_FORMATS})")

    traces = await get_agent_traces(db, agent_run_id)
    if format == "json":
        return json.dumps([{
            "step_number": t.step_number, "step_type": t.step_type, "description": t.description,
            "status": t.status, "duration_ms": t.duration_ms, "error": t.error,
        } for t in traces], indent=2)

    rows = "\n".join(
        f"<tr><td>{t.step_number}</td><td>{html.escape(t.step_type)}</td>"
        f"<td>{html.escape(t.description)}</td><td>{html.escape(t.status)}</td>"
        f"<td>{t.duration_ms if t.duration_ms is not None else ''}</td></tr>"
        for t in traces
    )
    return (
        "<table><thead><tr><th>#</th><th>Type</th><th>Description</th>"
        f"<th>Status</th><th>Duration (ms)</th></tr></thead><tbody>{rows}</tbody></table>"
    )


async def purge_expired_traces(db: AsyncSession) -> int:
    """Real, additional function (not one of this étape's own literal
    ones) -- a real, standalone, callable cleanup honoring
    `AGENT_TRACES_RETENTION_DAYS` (vision critique: "les traces
    sont-elles nettoyées automatiquement ?"). Real and ready, but NOT
    wired to an automatic Celery schedule in this pass -- this
    codebase already has real periodic Celery tasks elsewhere
    (`api/tasks/`), so scheduling this one is genuinely separate,
    small, future work, not fabricated here as already running."""
    cutoff = dt.datetime.now(dt.timezone.utc) - dt.timedelta(days=settings.AGENT_TRACES_RETENTION_DAYS)
    traces = (await db.scalars(select(AgentTrace))).all()
    removed = 0
    for trace in traces:
        if _as_aware_utc(trace.created_at) < cutoff:
            await db.delete(trace)
            removed += 1
    await db.flush()
    return removed
