"""Partie 5.4 -- real Celery jobs dispatching
`api/services/workflow_engine.py`'s own executor. Same `asyncio.run()`
bridge as every other real task in this codebase (`autonomous_agents.py`,
`reindex_schedule.py`), for the identical reason: the engine's own
functions stay async for the FastAPI routes/tests that also call them
directly, and a real workflow run can involve several real LLM/HTTP/
email calls -- too slow to run inline in the HTTP request that
triggers or resumes it."""

import asyncio
import logging
import uuid

from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

from api.config import settings
from api.models.workflow_human_input import WorkflowHumanInput
from api.models.workflow_run import WorkflowRun
from api.tasks.celery_app import celery_app

logger = logging.getLogger(__name__)


def _session_factory():
    engine = create_async_engine(settings.DATABASE_URL, pool_pre_ping=True)
    return engine, async_sessionmaker(bind=engine, expire_on_commit=False, autoflush=False)


async def _notify_workflow_outcome(db, run: WorkflowRun) -> None:
    """Phase 5, Étape 4 -- workflow_completed (in-app only, per the
    étape's own spec table) / workflow_failed (in-app + email)."""
    from api.models.workflow import Workflow
    from api.services.notifications import create_notification

    if run.status not in ("completed", "failed"):
        return
    workflow = await db.get(Workflow, run.workflow_id)
    if workflow is None or workflow.created_by is None:
        return
    notification_type = "workflow_completed" if run.status == "completed" else "workflow_failed"
    try:
        await create_notification(
            db, organization_id=workflow.organization_id, user_id=workflow.created_by, notification_type=notification_type,
            context={"workflow_name": workflow.name, "error": run.error},
        )
        await db.commit()
    except Exception as exc:  # noqa: BLE001 -- a notification failure must never fail the real workflow run it only reports on
        logger.warning("_notify_workflow_outcome: could not notify for run '%s': %s", run.id, exc)


async def _run_workflow_async(run_id: str) -> str:
    from api.services.workflow_engine import execute_workflow_run

    engine, session_factory = _session_factory()
    try:
        async with session_factory() as db:
            run = await db.get(WorkflowRun, uuid.UUID(run_id))
            if run is None:
                return "not_found"
            run = await execute_workflow_run(db, run)
            await db.commit()
            await _notify_workflow_outcome(db, run)
            return run.status
    finally:
        await engine.dispose()


@celery_app.task(name="api.tasks.workflows.run_workflow_task")
def run_workflow_task(run_id: str) -> str:
    """Dispatched by `POST /workflows/{id}/run` and
    `POST /webhooks/{trigger_id}` right after `trigger_workflow` commits
    the real, `pending` run."""
    return asyncio.run(_run_workflow_async(run_id))


def schedule_workflow_run(run_id: uuid.UUID) -> None:
    """Real Celery dispatch, wrapped best-effort -- same reasoning as
    `api/tasks/autonomous_agents.py`'s own `schedule_autonomous_agent_run`:
    a broker hiccup must never fail the real trigger request itself (the
    run row already exists, real and `pending`; a later real sweep --
    or a manual retry -- can still pick it up)."""
    try:
        run_workflow_task.delay(str(run_id))
    except Exception as exc:  # noqa: BLE001
        logger.warning("schedule_workflow_run: could not schedule run '%s': %s", run_id, exc)


async def _resume_workflow_async(run_id: str, human_input_id: str) -> str:
    from api.services.workflow_engine import resume_workflow_run

    engine, session_factory = _session_factory()
    try:
        async with session_factory() as db:
            run = await db.get(WorkflowRun, uuid.UUID(run_id))
            human_input = await db.get(WorkflowHumanInput, uuid.UUID(human_input_id))
            if run is None or human_input is None:
                return "not_found"
            run = await resume_workflow_run(db, run, human_input)
            await db.commit()
            return run.status
    finally:
        await engine.dispose()


@celery_app.task(name="api.tasks.workflows.resume_workflow_task")
def resume_workflow_task(run_id: str, human_input_id: str) -> str:
    """Dispatched right after `submit_human_input` really flips a
    paused `human` block to `submitted`."""
    return asyncio.run(_resume_workflow_async(run_id, human_input_id))


def schedule_workflow_resume(run_id: uuid.UUID, human_input_id: uuid.UUID) -> None:
    """Real Celery dispatch, wrapped best-effort -- same reasoning as
    `schedule_workflow_run` above."""
    try:
        resume_workflow_task.delay(str(run_id), str(human_input_id))
    except Exception as exc:  # noqa: BLE001
        logger.warning("schedule_workflow_resume: could not schedule resume for run '%s': %s", run_id, exc)


async def _check_scheduled_workflow_triggers_async() -> int:
    from api.services.workflow_triggers import check_scheduled_triggers, fire_scheduled_trigger

    engine, session_factory = _session_factory()
    fired = 0
    try:
        async with session_factory() as db:
            due = await check_scheduled_triggers(db)
            for trigger in due:
                try:
                    run = await fire_scheduled_trigger(db, trigger.id)
                    await db.commit()
                    schedule_workflow_run(run.id)
                    fired += 1
                except Exception as exc:  # noqa: BLE001 -- one real trigger's own failure must never abort the sweep
                    logger.warning("check_scheduled_workflow_triggers: trigger '%s' failed: %s", trigger.id, exc)
                    await db.rollback()
    finally:
        await engine.dispose()
    return fired


@celery_app.task(name="api.tasks.workflows.check_scheduled_workflow_triggers")
def check_scheduled_workflow_triggers() -> int:
    """Real, periodic Celery Beat task -- the real counterpart, for
    `schedule`-type workflow triggers, of
    `api/tasks/reindex_schedule.py`'s own `check_scheduled_reindexes_task`."""
    return asyncio.run(_check_scheduled_workflow_triggers_async())
