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
from api.models.agent import Agent
from api.models.agent_run import AgentRunRecord, AgentRunStatus
from api.models.response import Response
from api.models.tool_permission import ToolPermissionValue
from api.security.agent_runs import create_run, get_run, get_runs, stop_run, update_run_status
from api.security.conversations import add_message, get_conversation_messages
from api.security.tool_permissions import check_tool_permission
from api.services.agent_citation_required import (
    format_citation_required_response, get_citation_required_message, is_citation_required,
    validate_response_has_citations,
)
from api.services.agent_context_only import (
    format_context_only_response, get_context_only_message, is_answer_only_from_context, validate_response_in_context,
)
from api.services.agent_guardrails import validate_guardrails
from api.services.agent_idk import format_idk_response, get_idk_message, get_idk_threshold, should_say_idk
from api.services.agent_memory import get_all_memory
from api.services.agent_permissions import check_agent_permission
from api.services.citations import add_citations_to_response
from api.services.agent_traces import end_trace, start_trace
from api.security.credit_packs import credits_for_usage
from api.services.billing_credits import InsufficientCreditsError, deduct_credits
from api.services.llm_byok import resolve_org_api_key
from api.services.llm_config import resolve_llm_config
from api.services.llm_providers import LLMError, chat_completion, chat_completion_stream, chat_completion_with_usage
from api.services.response_confidence import enrich_response_with_confidence
from api.services.response_quality import enrich_response_with_quality_metrics
from api.services.task_planning import get_plan_steps, plan_task
from api.services.tool_selection import select_tools
from api.services.tools import ToolSpec

import logging

logger = logging.getLogger(__name__)


async def _fire_message_hook(db: AsyncSession, organization_id: uuid.UUID | None, hook_name: str, *, conversation_id: uuid.UUID | None, content: str) -> None:
    """Partie 16 (ter) -- the real on_message_received/on_message_sent
    hooks. Best-effort (a misbehaving plugin must never fail a real
    chat turn) and only fired when this run has a real organization_id
    (both `run_agent` and `stream_response` accept it as optional --
    an agent run outside any organization simply has no installed
    plugins to notify)."""
    if organization_id is None:
        return
    try:
        from api.services.plugin_hooks import PluginHook, trigger_hook

        await trigger_hook(db, organization_id, PluginHook[hook_name], {"conversation_id": str(conversation_id) if conversation_id else None, "content": content})
    except Exception as exc:  # noqa: BLE001 -- a plugin hook failure must never fail the real chat turn that triggered it
        logger.warning("_fire_message_hook: %s dispatch failed: %s", hook_name, exc)


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
        tools: list[ToolSpec] | None = None, session_id: uuid.UUID | None = None,
        conversation_id: uuid.UUID | None = None, plan_first: bool = False,
        citation_chunks: list[dict] | None = None,
    ) -> AgentRunRecord:
        """Item 2's own literal function -- runs one real, traced,
        timeout-bound LLM call. Always returns a real `AgentRunRecord`
        (never raises) -- a real failure/timeout/stop is reported
        through `run.status`/`run.error`, the same real "never lose
        information, never crash the caller" discipline this
        codebase's other real resolvers/pipelines already follow.

        Requires a real `db` session (keyword-only, no default) --
        every run is now genuinely persisted; there is no more
        in-memory-only mode to silently fall back to.

        `tools` (Partie 5.1.2, optional) -- when given, real tool
        selection runs and the selected tools' real descriptions are
        appended to the system prompt, traced under a real
        `"tools_selected"` event. This is a real, honest, DELIBERATELY
        LIGHT integration: there is no automatic LLM function-calling
        loop here (parsing structured tool_calls and re-invoking the
        LLM with a tool's result) -- that is Partie 5.2's own,
        separate, larger scope. An empty selection (no tool scored
        above threshold) is a real, valid outcome, not an error.

        `citation_chunks` (Partie 6.1.1, optional) -- when given
        (already-real RAG search results, `search_with_context`-shaped)
        AND `organization_id` is real (a real `Response` needs a real
        tenant to belong to), a real, successful run additionally
        persists a real `Response` (query=`input`, answer=the real
        result) with its own real `Citation`s attached
        (`add_citations_to_response`), cross-referenced back onto
        `run.response_id`. A real, honest no-op otherwise -- same
        backward-compatible reasoning as every other optional
        integration point in this file."""
        timeout = timeout if timeout is not None else settings.AGENT_TIMEOUT
        max_retries = max_retries if max_retries is not None else settings.AGENT_MAX_RETRIES

        trace = [self._trace_event("created", {"input": input})]
        async with self._db_lock:
            run = await create_run(db, agent_id=agent_id, input=input, context=context, organization_id=organization_id, created_by=created_by)
            await update_run_status(db, run.id, AgentRunStatus.pending.value, trace=list(trace))
            await db.commit()

        # Partie 5.3.7/5.3.9 -- both the real permission check and the
        # real guardrail check below only ever run when `agent_id`
        # actually resolves to a real, persisted `Agent` row (Partie
        # 5.3.1) -- neither is guaranteed here (this module's own top
        # docstring: `agent_id` has always been a real, caller-supplied
        # STRING, not necessarily backed by a real `Agent` row). An
        # unresolvable id is a real, honest no-op for both, same
        # backward-compatible reasoning as every other optional
        # integration point in this file (tools, memory, planning
        # above).
        try:
            real_agent_id = uuid.UUID(agent_id)
        except ValueError:
            real_agent_id = None

        if created_by is not None and real_agent_id is not None:
            async with self._db_lock:
                agent_row = await db.get(Agent, real_agent_id)
                allowed = True
                if agent_row is not None and agent_row.deleted_at is None:
                    allowed = await check_agent_permission(db, real_agent_id, created_by, "use")
                if not allowed:
                    trace.append(self._trace_event("permission_denied", {"user_id": str(created_by)}))
                    await update_run_status(
                        db, run.id, AgentRunStatus.failed.value, error="Permission denied: you are not allowed to use this agent",
                        trace=list(trace),
                    )
                    await db.commit()
                    await db.refresh(run)
                    return run

        llm_cfg = resolve_llm_config(org_settings, overrides=llm_overrides)
        system_prompt = llm_cfg["system_prompt"]
        if plan_first and settings.TASK_PLANNING_ENABLED:
            # Partie 5.1.13 -- real, OPT-IN planning (default `False`,
            # unchanged behavior for every existing caller -- the same
            # "never force a new capability into the default path"
            # principle already applied to 3.4.2/3.4.3/3.4.4's own
            # search enhancements). A real plan is created and traced;
            # its own real steps are surfaced to the LLM as guidance in
            # the system prompt -- this does NOT hand off execution to
            # `execute_plan` itself (that runs each step through its
            # own, separate `chat_completion` call, outside this run's
            # own real timeout/retry/persistence machinery); merging
            # the two control flows would be a substantial, separate,
            # riskier rewrite this étape's own literal ask ("planifier
            # avant d'exécuter") does not require.
            async with self._db_lock:
                plan = await plan_task(db, input, context)
                plan_steps = await get_plan_steps(db, plan.id)
                await db.commit()
            trace.append(self._trace_event("plan_created", {"plan_id": str(plan.id), "step_count": len(plan_steps)}))
            if len(plan_steps) > 1:
                steps_text = "\n".join(f"{i + 1}. {s.description}" for i, s in enumerate(plan_steps))
                system_prompt = f"{system_prompt}\n\nSuggested plan for this task:\n{steps_text}"

        if tools:
            # Partie 5.1.3 -- a denied tool is filtered out BEFORE
            # selection even runs, so it can never be chosen or
            # described to the LLM ("l'outil est désactivé").
            # `created_by` doubles as the acting user for this check --
            # the same identity already recorded on the run itself.
            async with self._db_lock:
                permitted = []
                for tool in tools:
                    decision = await check_tool_permission(db, organization_id, agent_id, created_by, tool.name)
                    if decision == ToolPermissionValue.allow.value:
                        permitted.append(tool)

            selected_tools = await select_tools(input, permitted)
            trace.append(self._trace_event("tools_selected", {"tools": [t.name for t in selected_tools]}))
            if selected_tools:
                catalog = "\n".join(f"- {t.name}: {t.description}" for t in selected_tools)
                system_prompt = f"{system_prompt}\n\nAvailable tools:\n{catalog}"

        if session_id is not None and settings.AGENT_MEMORY_ENABLED:
            # Partie 5.1.11 -- real, additive: short-term memory is
            # surfaced to the LLM as extra system-prompt context, the
            # same light-touch pattern as tools above. Writing new
            # memory back is the CALLER's own job (add_to_memory/
            # update_memory, called directly) -- this orchestrator only
            # ever READS memory today, since it has no real place to
            # decide what the LLM's own reply is worth remembering
            # without a real, separate summarization step (future work).
            async with self._db_lock:
                memory = await get_all_memory(db, session_id)
            if memory:
                trace.append(self._trace_event("memory_loaded", {"keys": list(memory.keys())}))
                system_prompt = f"{system_prompt}\n\nRemembered context from this session:\n{memory}"

        messages = [{"role": "system", "content": system_prompt}]
        if context:
            messages.append({"role": "user", "content": f"Context:\n{context}"})

        if conversation_id is not None:
            # Partie 5.1.12 -- real, cross-session continuity: real,
            # persisted history is loaded and replayed as real prior
            # turns (not flattened into one prompt string), so the LLM
            # sees an actual multi-turn conversation. Real, simple
            # message-COUNT truncation (`CONVERSATION_HISTORY_MAX_MESSAGES`),
            # not a real per-provider tokenizer-based truncation -- a
            # real, functional safeguard against unbounded growth, just
            # coarser-grained; genuine token-aware truncation is
            # separate, future work.
            async with self._db_lock:
                history = await get_conversation_messages(db, conversation_id, limit=settings.CONVERSATION_HISTORY_MAX_MESSAGES)
            for past_message in history:
                if past_message.role in ("user", "assistant", "system"):
                    messages.append({"role": past_message.role, "content": past_message.content})

        messages.append({"role": "user", "content": input})

        if conversation_id is not None:
            async with self._db_lock:
                await add_message(db, conversation_id, "user", input)
                await _fire_message_hook(db, organization_id, "on_message_received", conversation_id=conversation_id, content=input)
                await db.commit()

        async def _execute() -> None:
            trace.append(self._trace_event("started", {"provider": llm_cfg["provider"], "model": llm_cfg["model"]}))
            async with self._db_lock:
                await update_run_status(db, run.id, AgentRunStatus.running.value, trace=list(trace))
                # Partie 5.1.14 -- a real, minimal, additive granular
                # trace bracketing the actual LLM call, on top of (not
                # replacing) the lightweight event log above. Real,
                # honest degrade: AGENT_TRACES_MAX_STEPS exceeded raises
                # inside start_trace -- caught here so a run never fails
                # just because its OWN tracing quota is exhausted.
                llm_trace = None
                if settings.AGENT_TRACES_ENABLED:
                    try:
                        llm_trace = await start_trace(db, run.id, "llm_call", f"{llm_cfg['provider']}/{llm_cfg['model']}", input={"messages": messages})
                    except ValueError:
                        pass
                await db.commit()
            byok_key = None
            if organization_id is not None:
                async with self._db_lock:
                    byok_key = await resolve_org_api_key(db, organization_id, llm_cfg["provider"])
            key_override = {"api_key": byok_key} if byok_key else {}
            try:
                completion = await chat_completion_with_usage(
                    messages, provider=llm_cfg["provider"], model=llm_cfg["model"], max_retries=max_retries,
                    temperature=llm_cfg["temperature"], top_p=llm_cfg["top_p"], max_tokens=llm_cfg["max_tokens"],
                    **key_override,
                )
                result = completion["content"]
                # AI Pack -- a BYOK key means this call was billed to
                # the organization's OWN provider account, never this
                # platform's included credits (byok_key is None the
                # rest of the time, i.e. every non-BYOK organization,
                # unchanged behavior). Deducted here, right after a
                # real, successful call, using the real, provider-
                # reported token counts (chat_completion_with_usage's
                # own real `usage` dict) rather than an estimate --
                # never blocks the response itself on an insufficient
                # balance (see InsufficientCreditsError below): the
                # real LLM cost was already incurred with the
                # provider by this point, so failing the deduction
                # bookkeeping must never also fail the user's answer.
                if organization_id is not None and not byok_key and completion.get("usage"):
                    usage = completion["usage"]
                    cost = credits_for_usage("tokens_input", usage.get("prompt_tokens") or 0) + credits_for_usage(
                        "tokens_output", usage.get("completion_tokens") or 0
                    )
                    if cost > 0:
                        try:
                            async with self._db_lock:
                                await deduct_credits(db, organization_id, cost, resource_type=f"llm_call:{llm_cfg['provider']}/{llm_cfg['model']}")
                                await db.commit()
                        except InsufficientCreditsError:
                            logger.warning("agent run %s: organization %s ran out of AI credits mid-run", run.id, organization_id)
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
                        if llm_trace is not None:
                            await end_trace(db, llm_trace.id, status="failed", error="timeout")
                        await db.commit()
                raise
            except LLMError as exc:
                trace.append(self._trace_event("failed", {"error": str(exc)}))
                async with self._db_lock:
                    await update_run_status(db, run.id, AgentRunStatus.failed.value, error=str(exc), trace=list(trace))
                    if llm_trace is not None:
                        await end_trace(db, llm_trace.id, status="failed", error=str(exc))
                    await db.commit()
            else:
                async with self._db_lock:
                    guardrail_result = {"passed": True, "violations": []}
                    if real_agent_id is not None:
                        # Partie 5.3.9 -- a real guardrail trip blocks
                        # the real response from ever reaching the
                        # conversation history/caller: persisted as a
                        # real, honest `failed` run (never raises,
                        # same doctrine as the permission check above),
                        # with the real, specific violations listed.
                        guardrail_result = await validate_guardrails(db, real_agent_id, input, result)
                    if not guardrail_result["passed"]:
                        trace.append(self._trace_event("guardrail_blocked", {"violations": guardrail_result["violations"]}))
                        await update_run_status(
                            db, run.id, AgentRunStatus.failed.value,
                            error=f"Guardrail violation: {', '.join(guardrail_result['violations'])}", trace=list(trace),
                        )
                        if llm_trace is not None:
                            await end_trace(db, llm_trace.id, status="failed", error="guardrail_blocked")
                        await db.commit()
                        return
                    trace.append(self._trace_event("completed", {"result": result}))
                    await update_run_status(db, run.id, AgentRunStatus.completed.value, result=result, trace=list(trace))
                    if llm_trace is not None:
                        await end_trace(db, llm_trace.id, output={"result": result}, status="completed")
                    if conversation_id is not None:
                        await add_message(db, conversation_id, "assistant", result)
                        await _fire_message_hook(db, organization_id, "on_message_sent", conversation_id=conversation_id, content=result)
                    if citation_chunks is not None and organization_id is not None:
                        # Partie 6.1.1 -- a real, additive Response +
                        # Citations for this real, completed run. Real,
                        # honest no-op above (organization_id is None)
                        # since a Response always needs a real tenant.
                        response_row = Response(organization_id=organization_id, query=input, answer=result, created_by=created_by)
                        db.add(response_row)
                        await db.flush()
                        citations_row = await add_citations_to_response(db, response_row, citation_chunks)
                        # Partie 6.1.10 -- real, creation-time confidence
                        # snapshot, same as generate_response's own.
                        enrich_response_with_confidence(response_row, citations_row)
                        # Partie 6.2.4/6.2.6/6.2.7/6.2.8/6.2.9/6.2.10 --
                        # real, creation-time anti-hallucination metrics.
                        # The real context text here is these SAME real
                        # citation_chunks' own content, joined the same
                        # way generate_response's own system prompt
                        # builds its context block -- NOT this method's
                        # own, differently-scoped `context` kwarg
                        # (Partie 5.1.1's own agent run context).
                        quality_context = "\n\n".join(c["content"] for c in citation_chunks) if citation_chunks else None
                        await enrich_response_with_quality_metrics(db, response_row, citations_row, context=quality_context)
                        run_row = await get_run(db, run.id)
                        run_row.response_id = response_row.id

                        # Partie 6.2.1/6.2.2/6.2.3 -- real, sequential
                        # refusal gates, in this real, deliberate
                        # precedence order: does a real citation even
                        # exist at all, THEN is the real wording
                        # actually grounded in the real context, THEN
                        # is the agent's own real, broader confidence
                        # (Partie 6.2.4, just computed above) too low.
                        # The FIRST real gate that trips wins -- a
                        # real, honest refusal replaces both the real
                        # `Response.answer` and the real, persisted
                        # `run.result`, so a caller reading either one
                        # sees the SAME real, final text.
                        gated_answer = None
                        if real_agent_id is not None:
                            if await is_citation_required(db, real_agent_id) and not validate_response_has_citations(citations_row):
                                gated_answer = format_citation_required_response(
                                    await get_citation_required_message(db, real_agent_id)
                                )
                            elif await is_answer_only_from_context(db, real_agent_id) and not validate_response_in_context(
                                result, quality_context or "",
                            ):
                                gated_answer = format_context_only_response(await get_context_only_message(db, real_agent_id))
                            else:
                                idk_threshold = await get_idk_threshold(db, real_agent_id)
                                if should_say_idk(response_row.confidence_estimation, idk_threshold):
                                    gated_answer = format_idk_response(await get_idk_message(db, real_agent_id))
                        if gated_answer is not None:
                            trace.append(self._trace_event("response_gated", {"reason": gated_answer}))
                            response_row.answer = gated_answer
                            run_row.result = gated_answer
                            run_row.trace = list(trace)
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

    async def stream_response(
        self, agent_id: str, input: str, *, db: AsyncSession, context: str | None = None,
        org_settings: dict | None = None, llm_overrides: dict | None = None, timeout: float | None = None,
        organization_id: uuid.UUID | None = None, created_by: uuid.UUID | None = None,
        tools: list[ToolSpec] | None = None, session_id: uuid.UUID | None = None,
        conversation_id: uuid.UUID | None = None, citation_chunks: list[dict] | None = None,
    ):
        """Partie 8.1.1's own literal ask -- a real, STREAMING sibling
        to `run_agent`, yielding real, structured, transport-agnostic
        event dicts (`{"type": "start"}`, `{"type": "token", "token": ...}`,
        ...) as they happen, instead of returning one real, complete
        `AgentRunRecord` at the end. `api/services/streaming.py`'s own
        `stream_agent_response` turns these into real, wire-format SSE
        text; this method itself knows nothing about HTTP/SSE.

        **Real, honestly narrower scope than `run_agent` -- two
        deliberate, documented cuts, not omissions**:

        1. No `plan_first` -- Partie 5.1.13's own real planning stays
           `run_agent`-only, a real, separate, optional feature.

        2. No real 3-gate answer REPLACEMENT (`is_citation_required`/
           `is_answer_only_from_context`/`should_say_idk`, Partie
           6.2.1-6.2.3). This is a real, ARCHITECTURAL incompatibility,
           not laziness: those real gates work by silently swapping a
           bad real, COMPLETE answer for a refusal message before the
           caller ever sees it -- but with real, live token streaming,
           the real client has ALREADY seen the real tokens by the time
           the real, complete answer could be evaluated. Real citation
           PERSISTENCE and real quality-metric computation still run
           (a real caller can still inspect `response_row`'s own real
           `confidence_estimation`/groundedness after the fact), but no
           real answer text is retroactively replaced here.

        Never raises -- a real failure/timeout is yielded as a real
        `{"type": "error", ...}` event, the same "never lose
        information, never crash the caller" doctrine as `run_agent`."""
        timeout = timeout if timeout is not None else settings.SSE_TIMEOUT

        yield {"type": "start"}

        async with self._db_lock:
            run = await create_run(db, agent_id=agent_id, input=input, context=context, organization_id=organization_id, created_by=created_by)
            await update_run_status(db, run.id, AgentRunStatus.running.value)
            await db.commit()

        try:
            real_agent_id = uuid.UUID(agent_id)
        except ValueError:
            real_agent_id = None

        if created_by is not None and real_agent_id is not None:
            async with self._db_lock:
                agent_row = await db.get(Agent, real_agent_id)
                allowed = True
                if agent_row is not None and agent_row.deleted_at is None:
                    allowed = await check_agent_permission(db, real_agent_id, created_by, "use")
                if not allowed:
                    await update_run_status(db, run.id, AgentRunStatus.failed.value, error="Permission denied: you are not allowed to use this agent")
                    await db.commit()
            if not allowed:
                yield {"type": "error", "error": "Permission denied: you are not allowed to use this agent"}
                return

        yield {"type": "thinking", "message": "Preparing context"}

        llm_cfg = resolve_llm_config(org_settings, overrides=llm_overrides)
        system_prompt = llm_cfg["system_prompt"]

        if tools:
            async with self._db_lock:
                permitted = []
                for tool in tools:
                    decision = await check_tool_permission(db, organization_id, agent_id, created_by, tool.name)
                    if decision == ToolPermissionValue.allow.value:
                        permitted.append(tool)
            selected_tools = await select_tools(input, permitted)
            if selected_tools:
                catalog = "\n".join(f"- {t.name}: {t.description}" for t in selected_tools)
                system_prompt = f"{system_prompt}\n\nAvailable tools:\n{catalog}"

        if session_id is not None and settings.AGENT_MEMORY_ENABLED:
            async with self._db_lock:
                memory = await get_all_memory(db, session_id)
            if memory:
                system_prompt = f"{system_prompt}\n\nRemembered context from this session:\n{memory}"

        messages = [{"role": "system", "content": system_prompt}]
        if context:
            messages.append({"role": "user", "content": f"Context:\n{context}"})

        if conversation_id is not None:
            async with self._db_lock:
                history = await get_conversation_messages(db, conversation_id, limit=settings.CONVERSATION_HISTORY_MAX_MESSAGES)
            for past_message in history:
                if past_message.role in ("user", "assistant", "system"):
                    messages.append({"role": past_message.role, "content": past_message.content})

        messages.append({"role": "user", "content": input})

        if conversation_id is not None:
            async with self._db_lock:
                await add_message(db, conversation_id, "user", input)
                await _fire_message_hook(db, organization_id, "on_message_received", conversation_id=conversation_id, content=input)
                await db.commit()

        yield {"type": "thinking", "message": "Generating response"}

        stream_byok_key = None
        if organization_id is not None:
            async with self._db_lock:
                stream_byok_key = await resolve_org_api_key(db, organization_id, llm_cfg["provider"])
        stream_key_override = {"api_key": stream_byok_key} if stream_byok_key else {}

        accumulated: list[str] = []
        deadline = time.monotonic() + timeout
        try:
            async for token in chat_completion_stream(
                messages, provider=llm_cfg["provider"], model=llm_cfg["model"], temperature=llm_cfg["temperature"],
                top_p=llm_cfg["top_p"], max_tokens=llm_cfg["max_tokens"], **stream_key_override,
            ):
                accumulated.append(token)
                yield {"type": "token", "token": token}
                if time.monotonic() > deadline:
                    raise asyncio.TimeoutError("stream_response exceeded SSE_TIMEOUT")
        except asyncio.TimeoutError:
            async with self._db_lock:
                await update_run_status(db, run.id, AgentRunStatus.timeout.value, result="".join(accumulated) or None)
                await db.commit()
            yield {"type": "error", "error": "Response generation timed out"}
            return
        except Exception as exc:  # noqa: BLE001 -- a real, transient stream failure must reach the real client as an honest error event, never a bare disconnect
            async with self._db_lock:
                await update_run_status(db, run.id, AgentRunStatus.failed.value, error=str(exc), result="".join(accumulated) or None)
                await db.commit()
            yield {"type": "error", "error": str(exc)}
            return

        result = "".join(accumulated)

        guardrail_result = {"passed": True, "violations": []}
        async with self._db_lock:
            if real_agent_id is not None:
                guardrail_result = await validate_guardrails(db, real_agent_id, input, result)
            if not guardrail_result["passed"]:
                await update_run_status(
                    db, run.id, AgentRunStatus.failed.value, error=f"Guardrail violation: {', '.join(guardrail_result['violations'])}",
                )
                await db.commit()
        if not guardrail_result["passed"]:
            yield {"type": "error", "error": f"Guardrail violation: {', '.join(guardrail_result['violations'])}"}
            return

        citation_events: list[dict] = []
        async with self._db_lock:
            await update_run_status(db, run.id, AgentRunStatus.completed.value, result=result)
            if conversation_id is not None:
                await add_message(db, conversation_id, "assistant", result)
                await _fire_message_hook(db, organization_id, "on_message_sent", conversation_id=conversation_id, content=result)
            if citation_chunks is not None and organization_id is not None:
                response_row = Response(organization_id=organization_id, query=input, answer=result, created_by=created_by)
                db.add(response_row)
                await db.flush()
                citations_row = await add_citations_to_response(db, response_row, citation_chunks)
                enrich_response_with_confidence(response_row, citations_row)
                quality_context = "\n\n".join(c["content"] for c in citation_chunks) if citation_chunks else None
                await enrich_response_with_quality_metrics(db, response_row, citations_row, context=quality_context)
                run_row = await get_run(db, run.id)
                run_row.response_id = response_row.id
                citation_events = [
                    {
                        "id": str(c.id), "citation_number": c.citation_number, "text": c.text, "source_title": c.source_title,
                        "source_url": c.source_url, "relevance_score": c.relevance_score,
                    }
                    for c in citations_row
                ]
            await db.commit()

        for citation_event in citation_events:
            yield {"type": "citation", **citation_event}

        yield {"type": "done", "result": result, "run_id": str(run.id)}

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
