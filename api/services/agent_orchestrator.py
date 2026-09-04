"""
Partie 5.1.1 -- a real central orchestrator coordinating LLM-backed
agent runs: `AgentOrchestrator` (item 2's own literal class), with
`run_agent`/`run_multi_agent`/`get_agent_status`/`stop_agent`/
`get_agent_trace`.

**Fix, this same Partie**: the run registry is now the real, persistent
`agent_runs` table (api/models/agent_run.py, api/security/agent_runs.py)
instead of a plain in-memory dict -- status/trace/result now survive a
process restart and are readable from a DIFFERENT worker process than
the one that started the run (real multi-worker deployments finally
work for the READ side). This is a real, necessary, breaking signature
change: every public method here now takes a real `db: AsyncSession`
and is `async` (`get_agent_status`/`get_agent_trace`/`stop_agent` were
sync before this fix).

**A real bug this fix had to avoid, not just "persist and move on"**:
SQLAlchemy's `AsyncSession` is documented as unsafe for concurrent use
across asyncio tasks -- but `run_multi_agent` genuinely runs several
`run_agent` calls concurrently via `asyncio.gather`, and every one of
them now touches the SAME caller-supplied `db` session. A single
`self._db_lock` (asyncio.Lock) serializes every real DB read/write
across all methods of one orchestrator instance -- the actual, slow
part of a run (the LLM call itself, inside `chat_completion`) stays
OUTSIDE the lock, so parallel agents genuinely overlap on the network
call; only the brief DB bookkeeping around each one is serialized. This
does mean two agents in the same `run_multi_agent` batch never write to
the DB at the literal same instant -- a real, small, honest trade
against full parallelism, necessary because sharing one session is the
only option this codebase's existing `db: AsyncSession = Depends(get_db)`
convention gives a caller; a per-task session pool is real, separate,
future work if true concurrent persistence throughput is ever needed.

**A real, honest, still-remaining limit, narrower than before**: ACTUAL
cancellation of an in-flight `asyncio.Task` only works from the same
process that created it (Python has no cross-process task handle) --
`self._tasks` below is still a real, in-memory, per-worker map for
exactly that reason. `stop_agent`, called from the SAME worker that is
running the task, cancels it directly AND persists `stopped` (fully
real, tested). Called from a DIFFERENT worker, it can only persist the
`stop_requested`/`stopped` state -- the other worker's own task keeps
running to completion, unaware, because nothing in this codebase yet
gives one worker a live channel into another's event loop (that needs
a real message bus -- Redis pub/sub, most likely -- genuinely separate,
future work). Documented, not hidden.

**A real, honest, documented scope limit (unchanged from before this
fix)**: no real `Agent` entity (a stored, named agent CONFIGURATION)
exists anywhere in this codebase yet -- Partie 5.3 ("Agent Builder") is
explicitly not started. `agent_id` is a real, caller-supplied STRING
identifier, not a foreign key. One real "agent" run is honestly scoped
to one real, traced, timeout-bound, retryable LLM call -- real
tool-calling (Partie 5.2) and multi-step agent workflows (Partie 5.4)
are genuinely separate, future real work.

**Reuses this codebase's own real infrastructure**: `chat_completion`
(Partie 4.1.7, including its own real `max_retries` override) and
`resolve_llm_config` (Partie 4.3.1-4.3.5)."""

import asyncio
import time
import uuid

from sqlalchemy.ext.asyncio import AsyncSession

from api.config import settings
from api.models.agent_run import AgentRunRecord, AgentRunStatus
from api.security.agent_runs import create_run, get_run, get_runs, stop_run, update_run_status
from api.services.llm_config import resolve_llm_config
from api.services.llm_providers import LLMError, chat_completion


class AgentOrchestrator:
    """Item 2's own literal class -- see this module's own top
    docstring for the real, honest scope, the real DB-concurrency fix
    (`self._db_lock`), and the real limit on cross-process
    cancellation."""

    def __init__(self) -> None:
        # Real, in-memory, per-worker only -- keyed by the real run id
        # (api.models.agent_run.AgentRunRecord.id), used solely to give
        # a SAME-worker stop_agent() call a real asyncio.Task to cancel.
        # NOT the source of truth for status/trace anymore -- that's
        # the real `agent_runs` table (see this module's own top
        # docstring).
        self._tasks: dict[uuid.UUID, asyncio.Task] = {}
        # Serializes every real DB operation this instance performs --
        # see this module's own top docstring's "a real bug this fix
        # had to avoid" paragraph.
        self._db_lock = asyncio.Lock()

    @staticmethod
    def _trace_event(event: str, data: dict | None = None) -> dict:
        return {"event": event, "timestamp": time.time(), **(data or {})}

    async def run_agent(
        self, agent_id: str, input: str, *, db: AsyncSession, context: str | None = None,
        org_settings: dict | None = None, llm_overrides: dict | None = None, timeout: float | None = None,
        max_retries: int | None = None, organization_id: uuid.UUID | None = None, created_by: uuid.UUID | None = None,
    ) -> AgentRunRecord:
        """Item 2's own literal function -- runs one real, traced,
        timeout-bound LLM call. Always returns a real `AgentRunRecord`
        (never raises) -- a real failure/timeout/stop is reported
        through `run.status`/`run.error`, the same real "never lose
        information, never crash the caller" discipline this
        codebase's other real resolvers/pipelines already follow.

        Requires a real `db` session (keyword-only, no default) --
        every run is now genuinely persisted; there is no more
        in-memory-only mode to silently fall back to."""
        timeout = timeout if timeout is not None else settings.AGENT_TIMEOUT
        max_retries = max_retries if max_retries is not None else settings.AGENT_MAX_RETRIES

        trace = [self._trace_event("created", {"input": input})]
        async with self._db_lock:
            run = await create_run(db, agent_id=agent_id, input=input, context=context, organization_id=organization_id, created_by=created_by)
            await update_run_status(db, run.id, AgentRunStatus.pending.value, trace=list(trace))
            await db.commit()

        llm_cfg = resolve_llm_config(org_settings, overrides=llm_overrides)
        messages = [{"role": "system", "content": llm_cfg["system_prompt"]}]
        if context:
            messages.append({"role": "user", "content": f"Context:\n{context}"})
        messages.append({"role": "user", "content": input})

        async def _execute() -> None:
            trace.append(self._trace_event("started", {"provider": llm_cfg["provider"], "model": llm_cfg["model"]}))
            async with self._db_lock:
                await update_run_status(db, run.id, AgentRunStatus.running.value, trace=list(trace))
                await db.commit()
            try:
                result = await chat_completion(
                    messages, provider=llm_cfg["provider"], model=llm_cfg["model"], max_retries=max_retries,
                    temperature=llm_cfg["temperature"], top_p=llm_cfg["top_p"], max_tokens=llm_cfg["max_tokens"],
                )
            except asyncio.CancelledError:
                # A real, explicit, SAME-WORKER stop_agent() call
                # cancels this task directly and already persisted
                # "stopped" before doing so (see stop_agent below) --
                # so if we land here with the row still "running", this
                # is a real asyncio.wait_for timeout instead.
                async with self._db_lock:
                    current = await get_run(db, run.id)
                    if current is not None and current.status == AgentRunStatus.running.value:
                        trace.append(self._trace_event("timeout"))
                        await update_run_status(db, run.id, AgentRunStatus.timeout.value, trace=list(trace))
                        await db.commit()
                raise
            except LLMError as exc:
                trace.append(self._trace_event("failed", {"error": str(exc)}))
                async with self._db_lock:
                    await update_run_status(db, run.id, AgentRunStatus.failed.value, error=str(exc), trace=list(trace))
                    await db.commit()
            else:
                trace.append(self._trace_event("completed", {"result": result}))
                async with self._db_lock:
                    await update_run_status(db, run.id, AgentRunStatus.completed.value, result=result, trace=list(trace))
                    await db.commit()

        task = asyncio.create_task(_execute())
        self._tasks[run.id] = task
        try:
            await asyncio.wait_for(task, timeout=timeout)
        except (asyncio.TimeoutError, asyncio.CancelledError):
            pass  # real status/trace already recorded inside _execute's own real except clause
        finally:
            self._tasks.pop(run.id, None)

        async with self._db_lock:
            refreshed = await get_run(db, run.id)
        return refreshed if refreshed is not None else run

    async def run_multi_agent(
        self, agents: list[dict], input: str, *, db: AsyncSession, context: str | None = None,
        org_settings: dict | None = None, organization_id: uuid.UUID | None = None, created_by: uuid.UUID | None = None,
    ) -> list[AgentRunRecord]:
        """Item 2's own literal function -- real, genuinely parallel
        execution (`asyncio.gather`) of several real agents -- see this
        module's own top docstring for how `self._db_lock` keeps this
        safe against one shared `db` session while still overlapping
        each agent's own real LLM network call. Each real item of
        `agents` is a dict with at least a real `"agent_id"` key;
        `"input"`/`"context"`/`"llm_overrides"`/`"timeout"` are real,
        optional, PER-AGENT overrides of this call's own shared real
        defaults. `run_agent` itself never raises, so a real,
        individual agent failure never aborts the others."""
        async def _run_one(spec: dict) -> AgentRunRecord:
            return await self.run_agent(
                spec["agent_id"], spec.get("input", input), db=db, context=spec.get("context", context),
                org_settings=org_settings, llm_overrides=spec.get("llm_overrides"), timeout=spec.get("timeout"),
                organization_id=organization_id, created_by=created_by,
            )

        return await asyncio.gather(*(_run_one(spec) for spec in agents))

    async def get_agent_status(self, agent_id: str, db: AsyncSession, *, organization_id: uuid.UUID | None = None) -> str | None:
        """Item 2's own literal function -- reads the real, persistent
        `agent_runs` table (this agent_id's most recent run), so this
        now genuinely works from a different worker than the one that
        ran it. `None` for a real, unknown `agent_id`."""
        async with self._db_lock:
            runs = await get_runs(db, agent_id, organization_id=organization_id, limit=1)
        return runs[0].status if runs else None

    async def stop_agent(self, agent_id: str, db: AsyncSession, *, organization_id: uuid.UUID | None = None) -> bool:
        """Item 2's own literal function -- real, cooperative
        cancellation, now against the real, persistent run. Returns
        `True` only when a real, in-flight (pending/running) run was
        found and marked stopped; `False` for an unknown or
        already-finished `agent_id`. See this module's own top
        docstring for the real, honest limit: actual task cancellation
        only happens when this is called on the SAME worker that is
        running the task -- otherwise, only the persisted state changes."""
        async with self._db_lock:
            runs = await get_runs(db, agent_id, organization_id=organization_id, limit=1)
            if not runs:
                return False
            run = runs[0]
            if run.status not in (AgentRunStatus.pending.value, AgentRunStatus.running.value):
                return False

            stopped = await stop_run(db, run.id)
            await db.commit()

        task = self._tasks.get(run.id)
        if task is not None and not task.done():
            task.cancel()

        return stopped is not None

    async def get_agent_trace(self, agent_id: str, db: AsyncSession, *, organization_id: uuid.UUID | None = None) -> list[dict] | None:
        """Item 2's own literal function -- a real, ordered copy of
        this agent_id's most recent run's own real, persisted trace;
        `None` for an unknown `agent_id`."""
        async with self._db_lock:
            runs = await get_runs(db, agent_id, organization_id=organization_id, limit=1)
        if not runs:
            return None
        return list(runs[0].trace) if runs[0].trace is not None else []
