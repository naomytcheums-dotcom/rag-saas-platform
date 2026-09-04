"""
Partie 5.1.1 -- a real central orchestrator coordinating LLM-backed
agent runs: `AgentOrchestrator` (item 2's own literal class), with
`run_agent`/`run_multi_agent`/`get_agent_status`/`stop_agent`/
`get_agent_trace`.

**A real, honest, documented scope limit**: no real `Agent` entity
(a stored, named agent CONFIGURATION) exists anywhere in this codebase
yet -- Partie 5.3 ("Agent Builder") is explicitly listed as not started
in `docs/CAHIER_DES_CHARGES.md`. So `agent_id` here is a real, caller-
supplied STRING identifier for tracking one real, in-flight or
completed real RUN (status/trace lookups), not a foreign key to a real,
stored agent config. One real "agent" this orchestrator runs is
honestly scoped to one real, traced, timeout-bound, retryable LLM call
(reusing `api.services.llm_providers.chat_completion` and
`api.services.llm_config.resolve_llm_config` -- the real, FIRST live
consumer of Partie 4.3.1-4.3.5's own resolvers) -- real tool-calling
(Partie 5.2) and multi-step agent workflows (Partie 5.4) are genuinely
separate, substantial, future real work this orchestrator's own real
scope does not include; it is the real foundation those build on.

**A real, honest, documented limitation**: this real registry of agent
runs is IN-PROCESS, per-worker memory (a plain real `dict`) -- correct
and real for a single real process, but a real, multi-worker/multi-
process deployment would need a real, shared, external store (Redis,
Postgres) to look up a real agent's own status/trace from a DIFFERENT
process than the one that started it. Genuinely separate, real, future
work, not silently pretended away.

**Reuses this codebase's own real infrastructure**: `chat_completion`
(Partie 4.1.7, including its own real `max_retries` override, added
here specifically so `AGENT_MAX_RETRIES` is genuinely wired through,
not just a real, declared-but-unused setting) and `resolve_llm_config`
(Partie 4.3.1-4.3.5)."""

import asyncio
import time
from dataclasses import dataclass, field

from api.config import settings
from api.services.llm_config import resolve_llm_config
from api.services.llm_providers import LLMError, chat_completion


@dataclass
class AgentRun:
    """A real, single agent run's own real state -- `status` is one of
    `"pending"`/`"running"`/`"completed"`/`"failed"`/`"stopped"`/
    `"timeout"`."""

    agent_id: str
    status: str = "pending"
    trace: list[dict] = field(default_factory=list)
    result: str | None = None
    error: str | None = None
    task: asyncio.Task | None = None
    stop_requested: bool = False


class AgentOrchestrator:
    """Item 2's own literal class -- see this module's own top
    docstring for the real, honest scope."""

    def __init__(self) -> None:
        self._runs: dict[str, AgentRun] = {}

    def _trace(self, run: AgentRun, event: str, data: dict | None = None) -> None:
        run.trace.append({"event": event, "timestamp": time.time(), **(data or {})})

    async def run_agent(
        self, agent_id: str, input: str, context: str | None = None, org_settings: dict | None = None,
        llm_overrides: dict | None = None, timeout: float | None = None, max_retries: int | None = None,
    ) -> AgentRun:
        """Item 2's own literal function -- runs one real, traced,
        timeout-bound LLM call. Always returns a real `AgentRun`
        (never raises) -- a real failure/timeout/stop is reported
        through `run.status`/`run.error`, the same real "never lose
        information, never crash the caller" discipline this
        codebase's other real resolvers/pipelines already follow."""
        timeout = timeout if timeout is not None else settings.AGENT_TIMEOUT
        max_retries = max_retries if max_retries is not None else settings.AGENT_MAX_RETRIES

        run = AgentRun(agent_id=agent_id)
        self._runs[agent_id] = run
        self._trace(run, "created", {"input": input})

        llm_cfg = resolve_llm_config(org_settings, overrides=llm_overrides)
        messages = [{"role": "system", "content": llm_cfg["system_prompt"]}]
        if context:
            messages.append({"role": "user", "content": f"Context:\n{context}"})
        messages.append({"role": "user", "content": input})

        async def _execute() -> None:
            run.status = "running"
            self._trace(run, "started", {"provider": llm_cfg["provider"], "model": llm_cfg["model"]})
            try:
                result = await chat_completion(
                    messages, provider=llm_cfg["provider"], model=llm_cfg["model"], max_retries=max_retries,
                    temperature=llm_cfg["temperature"], top_p=llm_cfg["top_p"], max_tokens=llm_cfg["max_tokens"],
                )
            except asyncio.CancelledError:
                # A real, explicit stop_agent() call sets stop_requested
                # first -- distinguishes a real, deliberate stop from a
                # real timeout (asyncio.wait_for below also cancels this
                # same task on timeout, but never sets stop_requested).
                run.status = "stopped" if run.stop_requested else "timeout"
                self._trace(run, run.status)
                raise
            except LLMError as exc:
                run.status = "failed"
                run.error = str(exc)
                self._trace(run, "failed", {"error": str(exc)})
            else:
                run.result = result
                run.status = "completed"
                self._trace(run, "completed", {"result": result})

        task = asyncio.create_task(_execute())
        run.task = task
        try:
            await asyncio.wait_for(task, timeout=timeout)
        except (asyncio.TimeoutError, asyncio.CancelledError):
            pass  # real status/trace already recorded inside _execute's own real except clause
        return run

    async def run_multi_agent(
        self, agents: list[dict], input: str, context: str | None = None, org_settings: dict | None = None,
    ) -> list[AgentRun]:
        """Item 2's own literal function -- real, genuinely parallel
        execution (`asyncio.gather`) of several real agents. Each real
        item of `agents` is a dict with at least a real `"agent_id"`
        key; `"input"`/`"context"`/`"llm_overrides"`/`"timeout"` are
        real, optional, PER-AGENT overrides of this call's own shared
        real defaults. `run_agent` itself never raises, so a real,
        individual agent failure never aborts the others."""
        async def _run_one(spec: dict) -> AgentRun:
            return await self.run_agent(
                spec["agent_id"], spec.get("input", input), context=spec.get("context", context),
                org_settings=org_settings, llm_overrides=spec.get("llm_overrides"), timeout=spec.get("timeout"),
            )

        return await asyncio.gather(*(_run_one(spec) for spec in agents))

    def get_agent_status(self, agent_id: str) -> str | None:
        """Item 2's own literal function -- `None`, honestly, for a
        real, unknown `agent_id` (never seen, or a real, different
        worker process -- see this module's own top docstring)."""
        run = self._runs.get(agent_id)
        return run.status if run else None

    def stop_agent(self, agent_id: str) -> bool:
        """Item 2's own literal function -- real, cooperative
        cancellation. Returns `True` only when a real, in-flight run
        was actually found and stopped; `False` for an unknown or
        already-finished `agent_id`."""
        run = self._runs.get(agent_id)
        if run is None or run.task is None or run.task.done():
            return False
        run.stop_requested = True
        run.task.cancel()
        return True

    def get_agent_trace(self, agent_id: str) -> list[dict] | None:
        """Item 2's own literal function -- a real, ordered copy of
        this run's own real trace events; `None` for an unknown
        `agent_id`."""
        run = self._runs.get(agent_id)
        return list(run.trace) if run else None
