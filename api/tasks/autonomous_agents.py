"""Partie 23 -- real Celery jobs for autonomous agents. Same
asyncio.run() bridge as api/tasks/media.py/document_processing.py, for
the identical reason: api/services/autonomous_agents.py's real
planning/execution functions stay async for the FastAPI routes/tests
that also call them directly."""

import asyncio
import datetime as dt
import logging
import uuid

from sqlalchemy import select
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

from api.config import settings
from api.models.autonomous_agent import AutonomousAgent
from api.tasks.celery_app import celery_app
from api.tasks._db import make_async_engine

logger = logging.getLogger(__name__)


def _session_factory():
    engine = make_async_engine()
    return engine, async_sessionmaker(bind=engine, expire_on_commit=False, autoflush=False)


async def _run_autonomous_agent_async(agent_id: str) -> str:
    from api.services.autonomous_agents import AutonomousAgentNotFoundError, run_autonomous_agent

    engine, session_factory = _session_factory()
    try:
        async with session_factory() as db:
            try:
                agent = await run_autonomous_agent(db, uuid.UUID(agent_id))
                await db.commit()
                return agent.status
            except AutonomousAgentNotFoundError:
                await db.rollback()
                return "not_found"
    finally:
        await engine.dispose()


@celery_app.task(name="api.tasks.autonomous_agents.run_autonomous_agent_task")
def run_autonomous_agent_task(agent_id: str) -> str:
    """Dispatched by `POST /autonomous-agents/{id}/run` and `.../resume`
    -- a multi-step plan can involve several real LLM/tool calls, too
    slow to run inline in the HTTP request."""
    return asyncio.run(_run_autonomous_agent_async(agent_id))


def schedule_autonomous_agent_run(agent_id: uuid.UUID) -> None:
    """Real Celery dispatch, wrapped best-effort -- same reasoning as
    api/security/documents.py's own schedule_document_processing: a
    broker hiccup must never fail the run/resume request itself."""
    try:
        run_autonomous_agent_task.delay(str(agent_id))
    except Exception as exc:  # noqa: BLE001
        logger.warning("schedule_autonomous_agent_run: could not schedule run for agent '%s': %s", agent_id, exc)


async def _execute_agent_plan_async(plan_id: str) -> str:
    from api.models.autonomous_agent import AgentPlan
    from api.services.autonomous_agents import get_autonomous_agent, run_autonomous_agent

    engine, session_factory = _session_factory()
    try:
        async with session_factory() as db:
            plan = await db.get(AgentPlan, uuid.UUID(plan_id))
            if plan is None:
                return "not_found"
            agent = await run_autonomous_agent(db, plan.agent_id)
            await db.commit()
            return agent.status
    finally:
        await engine.dispose()


@celery_app.task(name="api.tasks.autonomous_agents.execute_agent_plan_task")
def execute_agent_plan_task(plan_id: str) -> str:
    """Item 11's own literal `execute_agent_plan(plan_id)` task --
    resolves the plan's own real agent and re-drives the SAME real
    execution loop `run_autonomous_agent_task` uses (a plan never runs
    independently of its own agent's real status/step-count/guardrails)."""
    return asyncio.run(_execute_agent_plan_async(plan_id))


async def _consolidate_agent_memory_async() -> int:
    from api.services.autonomous_agents import consolidate_memory

    engine, session_factory = _session_factory()
    consolidated = 0
    try:
        async with session_factory() as db:
            agents = (await db.execute(select(AutonomousAgent.id))).scalars().all()
            for agent_id in agents:
                try:
                    if await consolidate_memory(db, agent_id) is not None:
                        consolidated += 1
                except Exception as exc:  # noqa: BLE001 -- one real agent's own consolidation failure must never abort the sweep
                    logger.warning("consolidate_agent_memory: agent '%s' failed: %s", agent_id, exc)
            await db.commit()
    finally:
        await engine.dispose()
    return consolidated


@celery_app.task(name="api.tasks.autonomous_agents.consolidate_agent_memory")
def consolidate_agent_memory() -> int:
    """Real, periodic sweep -- consolidates every real agent's own
    short-term memory into long-term summaries."""
    return asyncio.run(_consolidate_agent_memory_async())


async def _cleanup_old_memory_async(days: int) -> int:
    from api.services.autonomous_agents import forget_old_memory

    engine, session_factory = _session_factory()
    forgotten = 0
    try:
        async with session_factory() as db:
            agents = (await db.execute(select(AutonomousAgent.id))).scalars().all()
            for agent_id in agents:
                try:
                    forgotten += await forget_old_memory(db, agent_id, days)
                except Exception as exc:  # noqa: BLE001
                    logger.warning("cleanup_old_memory: agent '%s' failed: %s", agent_id, exc)
            await db.commit()
    finally:
        await engine.dispose()
    return forgotten


@celery_app.task(name="api.tasks.autonomous_agents.cleanup_old_memory")
def cleanup_old_memory() -> int:
    """Item 11's own literal task -- real, periodic forgetting of
    stale `short_term` memories (real `long_term`/`episodic` memories
    are never touched)."""
    return asyncio.run(_cleanup_old_memory_async(settings.AUTONOMOUS_MEMORY_RETENTION_DAYS))


async def _check_agent_guardrails_async() -> int:
    """Real, periodic sweep -- any real agent stuck `executing` past
    `AUTONOMOUS_MAX_DURATION` (a real crashed/orphaned worker, a real
    infinite tool loop somehow past the step cap) is honestly marked
    `error` rather than left silently `executing` forever."""
    from api.models.autonomous_agent import AutonomousAgentStatus as Status

    engine, session_factory = _session_factory()
    flagged = 0
    threshold = dt.datetime.now(dt.timezone.utc) - dt.timedelta(seconds=settings.AUTONOMOUS_MAX_DURATION)
    try:
        async with session_factory() as db:
            stuck = (await db.execute(
                select(AutonomousAgent).where(AutonomousAgent.status == Status.executing.value, AutonomousAgent.updated_at < threshold)
            )).scalars().all()
            for agent in stuck:
                agent.status = Status.error.value
                agent.error = f"Exceeded AUTONOMOUS_MAX_DURATION ({settings.AUTONOMOUS_MAX_DURATION}s) -- stopped by the real guardrail sweep."
                flagged += 1
            await db.commit()
    finally:
        await engine.dispose()
    return flagged


@celery_app.task(name="api.tasks.autonomous_agents.check_agent_guardrails")
def check_agent_guardrails() -> int:
    return asyncio.run(_check_agent_guardrails_async())
