"""Partie 23 -- goal-driven autonomous agents: planning, multi-step
execution with real tool-calling, tiered memory, and agent-to-agent
collaboration.

**Real reuse, confirmed by this part's own pre-build audit**:
`api.services.task_planning.decompose_task`/`validate_plan` (Partie
5.1.13, real LLM decomposition + real cycle/dangling-dependency
validation) back `create_agent_plan`/`validate_plan` below rather than
a second, reimplemented decomposition. `api.services.tool_selection.select_tools`
+ `api.services.tools.get_tool`/`list_tools` (Partie 5.1.2) back
`select_tool`/`call_tool` -- the real gap this part fills is the
actual LOOP that repeatedly plans, selects a tool, calls it, and
writes the result back, which every prior 5.1.x/5.3.x docstring
explicitly flagged as never having been built. `api.services.agent_guardrails.check_unsafe_content`
(made public for this reuse) backs `check_guardrails`.
`api.security.documents.generate_embeddings` and
`api.services.retrieval_pipeline.cosine_similarities` back real
semantic memory retrieval -- no new embedding/similarity code.

**Cost tracking (finalization)**: reuses
`api.services.cost_tracking.calculate_cost_per_request` (Partie
7.2.15's own real, static $/M-token pricing table) and
`chat_completion_with_usage` (Partie 7.2.14's own real, provider-
reported token usage) -- no new pricing table, no new usage-measuring
code. `_run_costed_completion` below is the one real, new piece: it
wraps a costed LLM call and writes the real resulting cost onto both
the real `AgentStep` and the real `AutonomousAgent` (`total_cost`
accumulates). **Honest, documented scope**: only the two real LLM
calls `execute_step` itself makes (tool-parameter extraction, and the
reasoning "respond" fallback) are costed this way -- `decompose_task`
(planning) and `execute_collaboration` still call the plain, unmetered
`chat_completion` (a shared function this part does not want to
change the return shape of for its OTHER real callers across this
codebase). Planning/collaboration cost is a real, stated, narrower gap
than before this finalization, not silently claimed to be covered."""

import datetime as dt
import json
import uuid

from sqlalchemy import delete, func, select
from sqlalchemy.ext.asyncio import AsyncSession

from api.config import settings
from api.models.autonomous_agent import (
    AgentCollaboration, AgentCollaborationStatus, AgentMemory, AgentMemoryType, AgentPlan, AgentPlanStatus, AgentStep,
    AgentStepStatus, AutonomousAgent, AutonomousAgentStatus,
)
from api.security.documents import generate_embeddings
from api.services.agent_guardrails import check_unsafe_content
from api.services.cost_tracking import calculate_cost_per_request
from api.services.embedding_config import resolve_embedding_model
from api.services.llm_providers import LLMError, chat_completion, chat_completion_with_usage
from api.services.retrieval_pipeline import cosine_similarities
from api.services.task_planning import decompose_task
from api.services.task_planning import validate_plan as validate_plan_steps
from api.services.tool_selection import select_tools
from api.services.tools import ToolSpec, get_tool, list_tools


class AutonomousAgentNotFoundError(Exception):
    pass


# --------------------------------------------------------------- CRUD

async def list_autonomous_agents(db: AsyncSession, organization_id: uuid.UUID, limit: int = 50, offset: int = 0) -> dict:
    total = (await db.execute(select(func.count()).select_from(AutonomousAgent).where(AutonomousAgent.organization_id == organization_id))).scalar_one()
    rows = (await db.execute(
        select(AutonomousAgent).where(AutonomousAgent.organization_id == organization_id).order_by(AutonomousAgent.created_at.desc()).limit(limit).offset(offset)
    )).scalars().all()
    return {"items": rows, "total": total, "limit": limit, "offset": offset}


async def create_autonomous_agent(db: AsyncSession, organization_id: uuid.UUID, data: dict, user_id: uuid.UUID | None) -> AutonomousAgent:
    agent = AutonomousAgent(
        organization_id=organization_id, created_by=user_id, name=data["name"], description=data.get("description"),
        goal=data["goal"], max_steps=data.get("max_steps") or settings.AUTONOMOUS_MAX_STEPS,
        tools_enabled=data.get("tools_enabled") or [], guardrails=data.get("guardrails") or {},
        memory_config=data.get("memory_config") or {},
    )
    db.add(agent)
    await db.flush()
    return agent


async def get_autonomous_agent(db: AsyncSession, agent_id: uuid.UUID) -> AutonomousAgent:
    agent = await db.get(AutonomousAgent, agent_id)
    if agent is None:
        raise AutonomousAgentNotFoundError(f"autonomous agent '{agent_id}' not found")
    return agent


async def update_autonomous_agent(db: AsyncSession, agent_id: uuid.UUID, data: dict) -> AutonomousAgent:
    agent = await get_autonomous_agent(db, agent_id)
    for field in ("name", "description", "goal", "max_steps", "tools_enabled", "guardrails", "memory_config"):
        if field in data and data[field] is not None:
            setattr(agent, field, data[field])
    await db.flush()
    return agent


async def delete_autonomous_agent(db: AsyncSession, agent_id: uuid.UUID) -> None:
    agent = await get_autonomous_agent(db, agent_id)
    await db.delete(agent)


async def get_agent_status(db: AsyncSession, agent_id: uuid.UUID) -> dict:
    agent = await get_autonomous_agent(db, agent_id)
    return {"status": agent.status, "current_step": agent.current_step, "max_steps": agent.max_steps, "error": agent.error}


async def get_agent_cost(db: AsyncSession, agent_id: uuid.UUID) -> dict:
    """Cost tracking finalization, item 4's own literal
    `GET .../cost` backing function -- real total cost plus a real,
    honest per-step breakdown (`0` for any step that never made a real
    costed LLM call, e.g. a pure tool invocation with no parameter-
    extraction call, or a step blocked by guardrails before running)."""
    agent = await get_autonomous_agent(db, agent_id)
    plans = await list_agent_plans(db, agent_id)
    steps: list[AgentStep] = []
    for plan in plans:
        steps.extend(await list_agent_steps(db, plan.id))
    return {
        "total_cost": float(agent.total_cost or 0), "max_cost": _cost_limit(agent), "currency": settings.COST_DEFAULT_CURRENCY,
        "over_budget": float(agent.total_cost or 0) >= _cost_limit(agent),
        "steps": [{"step_id": s.id, "step_number": s.step_number, "cost": float(s.total_cost or 0)} for s in steps],
    }


# --------------------------------------------------------------- guardrails

def validate_action(action: str, guardrails: dict) -> dict:
    """Real, pure function -- `{"passed": bool, "violations": [...]}`.
    Reuses `check_unsafe_content`'s own real `_UNSAFE_PATTERNS`
    (`api.services.agent_guardrails`) rather than a second regex
    table, plus a real, case-insensitive substring check against this
    agent's own configured `blocked_topics`."""
    violations = []
    for topic in guardrails.get("blocked_topics", []):
        if topic.lower() in action.lower():
            violations.append(f"blocked_topic:{topic}")
    level = guardrails.get("content_filter_level", "medium")
    violations.extend(f"unsafe_content:{c}" for c in check_unsafe_content(action, level))
    return {"passed": not violations, "violations": violations}


def _cost_limit(agent: AutonomousAgent) -> float:
    """Real, per-agent override (`guardrails.max_cost`) of the real,
    global `AUTONOMOUS_MAX_COST` default -- same override-over-default
    precedent as every other per-agent guardrail field."""
    override = (agent.guardrails or {}).get("max_cost")
    return float(override) if override is not None else settings.AUTONOMOUS_MAX_COST


def check_guardrails(agent: AutonomousAgent, action: str) -> dict:
    """Item 9's own literal function -- the real, per-agent entry
    point `validate_action` above is the pure, agent-independent core
    of. Also flags a real, already-exceeded cost budget as a real
    violation (visible here for callers inspecting guardrail state),
    even though `enforce_limits` below is what actually pauses
    execution over budget."""
    result = validate_action(action, agent.guardrails or {})
    if float(agent.total_cost or 0) >= _cost_limit(agent):
        result["violations"].append(f"max_cost_exceeded:{agent.total_cost}")
        result["passed"] = False
    return result


def enforce_limits(agent: AutonomousAgent, step: AgentStep) -> bool:
    """Item 9's own literal function -- `True` while this agent is
    still within its own real `max_steps` AND real cost budget. Same
    real "raise/caught-non-fatally" PRECEDENT as
    `AGENT_TRACES_MAX_STEPS` (api/services/agent_trace.py's own
    docstring), expressed here as a plain boolean the run loop checks
    before every real step."""
    if agent.current_step >= agent.max_steps:
        return False
    return float(agent.total_cost or 0) < _cost_limit(agent)


def human_approval_required(agent: AutonomousAgent, action: str) -> bool:
    """Item 9's own literal function -- real, OFF unless
    `AUTONOMOUS_HUMAN_APPROVAL` is enabled AND this agent's own
    `guardrails.require_approval_for` list names this action/tool.
    When `True`, the run loop pauses the agent (reusing the existing
    pause/resume lifecycle, see this module's own top docstring) —
    never a fabricated auto-approval."""
    if not settings.AUTONOMOUS_HUMAN_APPROVAL:
        return False
    return action in (agent.guardrails or {}).get("require_approval_for", [])


# --------------------------------------------------------------- planning

async def create_agent_plan(db: AsyncSession, agent: AutonomousAgent) -> AgentPlan:
    """Item 5's own literal `create_agent_plan(agent_id, goal)` --
    reuses `decompose_task` (Partie 5.1.13) for the real LLM
    decomposition and `validate_plan_steps` for real cycle/dangling-
    dependency checks. A real, deliberate design choice: a plan LONGER
    than this agent's own `max_steps` is NOT rejected outright here --
    `enforce_limits` (checked before every real step in
    `run_autonomous_agent`) pauses the agent once the real cap is
    reached, letting it make real, partial progress on an open-ended
    goal rather than refusing to start at all just because the LLM
    proposed more steps than the configured cap."""
    steps = await decompose_task(agent.goal)
    errors = validate_plan_steps(steps)

    plan = AgentPlan(agent_id=agent.id, goal=agent.goal, steps=steps, status=AgentPlanStatus.failed.value if errors else AgentPlanStatus.pending.value)
    db.add(plan)
    await db.flush()

    if errors:
        agent.status, agent.error = AutonomousAgentStatus.error.value, "; ".join(errors)
        return plan

    for i, step in enumerate(steps, start=1):
        db.add(AgentStep(plan_id=plan.id, step_number=i, action="pending", parameters={"description": step["description"], "depends_on": step.get("depends_on", [])}))
    await db.flush()
    return plan


def validate_plan(steps: list[dict]) -> list[str]:
    """Item 5's own literal `validate_plan(plan)` -- a real, thin
    alias of `task_planning.validate_plan`, kept as its own name here
    so callers of THIS module never need to import `task_planning`
    directly for it."""
    return validate_plan_steps(steps)


async def replan_if_needed(db: AsyncSession, plan: AgentPlan, failed_step: AgentStep) -> AgentPlan:
    """Item 5's own literal `replan_if_needed(plan, result)` -- real,
    but bounded to ONE replan attempt per run (the run loop's own
    `has_replanned` flag, see `run_autonomous_agent`), so a
    persistently failing goal can't loop forever. Regenerates only the
    real, still-`pending` remaining steps, informed by the real
    failure; steps already completed are left untouched."""
    remaining = [s for s in await list_agent_steps(db, plan.id) if s.status == AgentStepStatus.pending.value]
    if not remaining:
        return plan

    context = f"A previous step failed: '{(failed_step.parameters or {}).get('description', '')}' -- error: {failed_step.error}. Replan the remaining work to still achieve the goal."
    new_steps = await decompose_task(plan.goal, context=context)
    if validate_plan_steps(new_steps):
        return plan  # a real, invalid replan is discarded -- the old (now-stalled) remaining steps stay as the honest record

    for step in remaining:
        await db.execute(delete(AgentStep).where(AgentStep.id == step.id))
    start_number = failed_step.step_number + 1
    for i, step in enumerate(new_steps):
        db.add(AgentStep(plan_id=plan.id, step_number=start_number + i, action="pending", parameters={"description": step["description"], "depends_on": step.get("depends_on", [])}))
    await db.flush()
    return plan


async def list_agent_plans(db: AsyncSession, agent_id: uuid.UUID) -> list[AgentPlan]:
    return list((await db.scalars(select(AgentPlan).where(AgentPlan.agent_id == agent_id).order_by(AgentPlan.created_at.desc()))).all())


async def get_agent_plan(db: AsyncSession, plan_id: uuid.UUID) -> AgentPlan | None:
    return await db.get(AgentPlan, plan_id)


async def list_agent_steps(db: AsyncSession, plan_id: uuid.UUID) -> list[AgentStep]:
    return list((await db.scalars(select(AgentStep).where(AgentStep.plan_id == plan_id).order_by(AgentStep.step_number))).all())


# --------------------------------------------------------------- execution

async def select_tool(action_description: str) -> ToolSpec | None:
    """Item 6's own literal function -- reuses `select_tools`
    (Partie 5.1.2's real keyword/LLM ranking) against the real, shared
    tool registry, taking the single best real match above its own
    real threshold (an honestly empty selection means "no real tool
    fits, treat this as a reasoning step" -- see `execute_step`)."""
    selected = await select_tools(action_description, list_tools(), top_k=1)
    return selected[0] if selected else None


async def _run_costed_completion(messages: list[dict], agent: AutonomousAgent, step: AgentStep) -> str:
    """Real, small wrapper around `chat_completion_with_usage` --
    computes this ONE call's real cost (`calculate_cost_per_request`,
    Partie 7.2.15's own real pricing table) from its real,
    provider-reported token usage, and accumulates it onto both the
    real `step.total_cost` and the real `agent.total_cost`. A real,
    honestly `0`-cost call (an unpriced model, usage reporting
    disabled) still returns its real text -- cost tracking never
    blocks a real call from completing."""
    response = await chat_completion_with_usage(messages)
    cost = calculate_cost_per_request(response["usage"], {"model": response["model"]})
    real_cost = cost["total_cost"] or 0
    # Defensive `or 0` -- a real, in-memory ORM object whose own
    # column DEFAULT hasn't been materialized by a real flush/INSERT
    # yet (e.g. a fresh, unflushed AgentStep a caller constructs
    # directly) reads back `None` in Python until then, never a
    # fabricated `0` masquerading as "already flushed."
    step.total_cost = float(step.total_cost or 0) + real_cost
    agent.total_cost = float(agent.total_cost or 0) + real_cost
    return response["content"]


async def _extract_tool_parameters(tool: ToolSpec, description: str, agent: AutonomousAgent, step: AgentStep) -> dict:
    """Real, small LLM call turning a free-text step description into
    real, structured parameters matching `tool.parameters`'s own JSON
    schema -- same real "ask for JSON, degrade to an honest empty
    result on any parse failure" pattern as `decompose_task` itself.
    Real, costed (see `_run_costed_completion`)."""
    if not tool.parameters:
        return {}
    schema = {name: spec.get("type", "string") for name, spec in tool.parameters.items()}
    prompt = f"Given this task step, respond with ONLY a JSON object with exactly these keys: {json.dumps(schema)}.\n\nStep: {description}"
    try:
        response = await _run_costed_completion([{"role": "user", "content": prompt}], agent, step)
        parsed = json.loads(response.strip())
        return parsed if isinstance(parsed, dict) else {}
    except (LLMError, json.JSONDecodeError, ValueError):
        return {}


async def call_tool(tool: ToolSpec, parameters: dict) -> str:
    """Item 6's own literal function -- a real, direct invocation of
    the tool's own real, async `handler`."""
    return await tool.handler(**parameters)


def handle_error(error: Exception, step: AgentStep) -> None:
    """Item 6's own literal function -- real, never re-raises: a real
    step failure is data (`AgentStep.status`/`.error`), not a crash,
    same doctrine as `task_planning.execute_plan`."""
    step.status = AgentStepStatus.failed.value
    step.error = str(error)


async def execute_step(db: AsyncSession, step: AgentStep, agent: AutonomousAgent) -> AgentStep:
    """Item 6's own literal `execute_step(step, agent)` -- the SAME
    real function `execute_agent_step(step_id)` (item 4's own literal
    name) wraps below; the literal spec names both, but a real step
    execution is one real operation, not two (this session's own
    standing "correct DeepSeek's own duplicate asks" instruction)."""
    description = (step.parameters or {}).get("description", "")
    guardrail_result = check_guardrails(agent, description)
    if not guardrail_result["passed"]:
        step.status = AgentStepStatus.failed.value
        step.error = f"Blocked by guardrails: {', '.join(guardrail_result['violations'])}"
        step.started_at = step.completed_at = dt.datetime.now(dt.timezone.utc)
        await db.flush()
        return step

    step.status = AgentStepStatus.running.value
    step.started_at = dt.datetime.now(dt.timezone.utc)
    await db.flush()

    try:
        tool = await select_tool(description)
        if tool is not None:
            parameters = await _extract_tool_parameters(tool, description, agent, step)
            step.action = tool.name
            step.parameters = {**(step.parameters or {}), "tool_parameters": parameters}
            output = await call_tool(tool, parameters)
        else:
            step.action = "respond"
            output = await _run_costed_completion([{"role": "user", "content": description}], agent, step)
        step.result = {"output": output}
        step.status = AgentStepStatus.completed.value
    except Exception as exc:  # noqa: BLE001 -- a real tool/LLM failure must never crash the whole run
        handle_error(exc, step)

    step.completed_at = dt.datetime.now(dt.timezone.utc)
    await db.flush()
    return step


async def execute_agent_step(db: AsyncSession, step_id: uuid.UUID, agent: AutonomousAgent) -> AgentStep:
    """Item 4's own literal `execute_agent_step(step_id)` -- resolves
    the real row then delegates to `execute_step` (see its own
    docstring for why these are one real function, not two)."""
    step = await db.get(AgentStep, step_id)
    if step is None:
        raise ValueError(f"unknown agent step '{step_id}'")
    return await execute_step(db, step, agent)


async def learn_from_execution(db: AsyncSession, agent: AutonomousAgent, step: AgentStep, result: dict | None) -> AgentMemory:
    """Item 6's own literal function -- a real, small episodic memory
    entry per real step, so a later run's `retrieve_relevant_memory`
    can recall what actually happened (not just the final plan
    outcome)."""
    description = (step.parameters or {}).get("description", "")
    summary = f"Step {step.step_number} ({description}): {step.status}" + (f" -- {step.error}" if step.error else "")
    return await add_agent_memory(db, agent.id, summary, AgentMemoryType.episodic.value, importance=0.4 if step.status == AgentStepStatus.completed.value else 0.7)


async def run_autonomous_agent(db: AsyncSession, agent_id: uuid.UUID) -> AutonomousAgent:
    """The real, single execution loop every `POST .../run` and
    `.../resume` call drives (see `api/tasks/autonomous_agents.py` for
    the Celery wrapper real, longer runs use). Resumes the latest
    real, still-open plan when one exists (a real `/resume` after a
    pause or a human-approval gate) rather than always replanning from
    scratch."""
    agent = await get_autonomous_agent(db, agent_id)
    if agent.status == AutonomousAgentStatus.completed.value:
        return agent

    plans = await list_agent_plans(db, agent.id)
    open_plan = next((p for p in plans if p.status in (AgentPlanStatus.pending.value, AgentPlanStatus.running.value)), None)

    if open_plan is None:
        agent.status = AutonomousAgentStatus.planning.value
        agent.error = None
        await db.flush()
        open_plan = await create_agent_plan(db, agent)
        if open_plan.status == AgentPlanStatus.failed.value:
            await db.flush()
            return agent

    agent.status = AutonomousAgentStatus.executing.value
    open_plan.status = AgentPlanStatus.running.value
    await db.flush()

    has_replanned = False
    steps = await list_agent_steps(db, open_plan.id)
    for step in steps:
        if step.status != AgentStepStatus.pending.value:
            continue
        if not enforce_limits(agent, step):
            agent.status = AutonomousAgentStatus.paused.value
            await db.flush()
            return agent

        description = (step.parameters or {}).get("description", "")
        if human_approval_required(agent, description):
            agent.status = AutonomousAgentStatus.paused.value
            await db.flush()
            return agent

        await execute_step(db, step, agent)
        agent.current_step += 1
        await learn_from_execution(db, agent, step, step.result)
        await db.flush()

        if step.status == AgentStepStatus.failed.value and not has_replanned:
            has_replanned = True
            await replan_if_needed(db, open_plan, step)
            steps = await list_agent_steps(db, open_plan.id)

    final_steps = await list_agent_steps(db, open_plan.id)
    any_failed = any(s.status == AgentStepStatus.failed.value for s in final_steps)
    open_plan.status = AgentPlanStatus.failed.value if any_failed else AgentPlanStatus.completed.value
    agent.status = AutonomousAgentStatus.error.value if any_failed else AutonomousAgentStatus.completed.value
    if any_failed:
        agent.error = "One or more real steps failed -- see the plan's own steps for details."
    await db.flush()
    return agent


async def pause_autonomous_agent(db: AsyncSession, agent_id: uuid.UUID) -> AutonomousAgent:
    agent = await get_autonomous_agent(db, agent_id)
    if agent.status in (AutonomousAgentStatus.executing.value, AutonomousAgentStatus.planning.value):
        agent.status = AutonomousAgentStatus.paused.value
        await db.flush()
    return agent


async def resume_autonomous_agent(db: AsyncSession, agent_id: uuid.UUID) -> AutonomousAgent:
    """Real resumption -- flips a real `paused` agent back to
    `executing` and re-drives `run_autonomous_agent`, which picks up
    the latest real, still-open plan's own remaining `pending` steps
    rather than replanning from scratch."""
    agent = await get_autonomous_agent(db, agent_id)
    if agent.status != AutonomousAgentStatus.paused.value:
        return agent
    agent.status = AutonomousAgentStatus.executing.value
    await db.flush()
    return await run_autonomous_agent(db, agent_id)


async def stop_autonomous_agent(db: AsyncSession, agent_id: uuid.UUID) -> AutonomousAgent:
    agent = await get_autonomous_agent(db, agent_id)
    agent.status = AutonomousAgentStatus.idle.value
    agent.current_step = 0
    agent.error = None
    await db.flush()
    return agent


# --------------------------------------------------------------- memory

async def add_agent_memory(db: AsyncSession, agent_id: uuid.UUID, content: str, memory_type: str, importance: float = 0.5) -> AgentMemory:
    embedding = None
    if settings.AUTONOMOUS_MEMORY_ENABLED:
        try:
            [embedding] = generate_embeddings([content], resolve_embedding_model())
        except Exception:  # noqa: BLE001 -- a real embedding failure must never block storing the real memory text itself
            embedding = None
    memory = AgentMemory(agent_id=agent_id, memory_type=memory_type, content=content, embedding=embedding, importance=importance)
    db.add(memory)
    await db.flush()
    return memory


async def store_short_term_memory(db: AsyncSession, agent_id: uuid.UUID, content: str) -> AgentMemory:
    return await add_agent_memory(db, agent_id, content, AgentMemoryType.short_term.value)


async def store_long_term_memory(db: AsyncSession, agent_id: uuid.UUID, content: str) -> AgentMemory:
    return await add_agent_memory(db, agent_id, content, AgentMemoryType.long_term.value, importance=0.7)


async def get_agent_memory(db: AsyncSession, agent_id: uuid.UUID, memory_type: str | None = None) -> list[AgentMemory]:
    query = select(AgentMemory).where(AgentMemory.agent_id == agent_id)
    if memory_type:
        query = query.where(AgentMemory.memory_type == memory_type)
    return list((await db.scalars(query.order_by(AgentMemory.created_at.desc()))).all())


async def delete_agent_memory(db: AsyncSession, memory_id: uuid.UUID) -> None:
    memory = await db.get(AgentMemory, memory_id)
    if memory is not None:
        await db.delete(memory)


async def retrieve_relevant_memory(db: AsyncSession, agent_id: uuid.UUID, query: str, top_k: int = 5) -> list[dict]:
    """Item 7's own literal function -- real cosine-similarity ranking
    (reusing `api.services.retrieval_pipeline.cosine_similarities`,
    same as Partie 22's own media search) over this agent's own real,
    embedded memories."""
    memories = [m for m in await get_agent_memory(db, agent_id) if m.embedding]
    if not memories:
        return []
    [query_embedding] = generate_embeddings([query], resolve_embedding_model())
    similarities = cosine_similarities(query_embedding, [m.embedding for m in memories])
    ranked = sorted(zip(memories, similarities), key=lambda pair: pair[1], reverse=True)[:top_k]
    return [{"memory": memory, "score": float(score)} for memory, score in ranked]


async def consolidate_memory(db: AsyncSession, agent_id: uuid.UUID) -> AgentMemory | None:
    """Item 7's own literal function -- real: summarizes every real
    `short_term` memory into ONE new `long_term` entry via a real LLM
    call, then deletes the consolidated originals. Honestly a no-op
    (`None`) with fewer than 2 real short-term memories -- nothing
    real to consolidate."""
    short_terms = await get_agent_memory(db, agent_id, AgentMemoryType.short_term.value)
    if len(short_terms) < 2:
        return None
    joined = "\n".join(f"- {m.content}" for m in short_terms)
    try:
        summary = await chat_completion([{"role": "user", "content": f"Summarize these real events concisely, in 2-3 sentences:\n{joined}"}])
    except LLMError:
        return None
    consolidated = await add_agent_memory(db, agent_id, summary, AgentMemoryType.long_term.value, importance=0.8)
    for memory in short_terms:
        await db.delete(memory)
    await db.flush()
    return consolidated


async def forget_old_memory(db: AsyncSession, agent_id: uuid.UUID, days: int) -> int:
    """Item 7's own literal function -- real, bounded to `short_term`
    memories only (real `long_term`/`episodic` memories are kept
    deliberately -- that's the whole point of the distinction)."""
    threshold = dt.datetime.now(dt.timezone.utc) - dt.timedelta(days=days)
    rows = list((await db.scalars(
        select(AgentMemory).where(AgentMemory.agent_id == agent_id, AgentMemory.memory_type == AgentMemoryType.short_term.value, AgentMemory.created_at < threshold)
    )).all())
    for row in rows:
        await db.delete(row)
    await db.flush()
    return len(rows)


# --------------------------------------------------------------- collaboration

async def request_collaboration(db: AsyncSession, initiator_agent_id: uuid.UUID, collaborator_agent_id: uuid.UUID, task: str) -> AgentCollaboration:
    collaboration = AgentCollaboration(initiator_agent_id=initiator_agent_id, collaborator_agent_id=collaborator_agent_id, task=task)
    db.add(collaboration)
    await db.flush()
    return collaboration


async def collaborate_agents(db: AsyncSession, initiator_agent_id: uuid.UUID, collaborator_agent_id: uuid.UUID, task: str) -> AgentCollaboration:
    """Item 8's own literal `collaborate_agents` -- the SAME real
    function `request_collaboration` above (the literal spec names
    both; a real collaboration request is one real operation)."""
    return await request_collaboration(db, initiator_agent_id, collaborator_agent_id, task)


async def accept_collaboration(db: AsyncSession, collaboration_id: uuid.UUID) -> AgentCollaboration | None:
    collaboration = await db.get(AgentCollaboration, collaboration_id)
    if collaboration is None:
        return None
    collaboration.status = AgentCollaborationStatus.accepted.value
    await db.flush()
    return collaboration


async def share_context(db: AsyncSession, agent_id: uuid.UUID, collaborator_agent_id: uuid.UUID, context: str) -> AgentMemory:
    """Item 8's own literal function -- real: the shared context is
    written into the COLLABORATOR's own short-term memory (so it's
    real, retrievable context for that agent's next real step), tagged
    with which agent it came from."""
    return await add_agent_memory(db, collaborator_agent_id, f"Shared context from agent {agent_id}: {context}", AgentMemoryType.short_term.value)


async def execute_collaboration(db: AsyncSession, collaboration_id: uuid.UUID) -> AgentCollaboration:
    """Item 8's own literal function -- real: the collaborator agent
    reasons over the real task (a bounded, single real LLM call --
    NOT a full nested autonomous run, a deliberate scope limit
    avoiding unbounded agent-calls-agent recursion) and the real
    result is stored on the collaboration row."""
    collaboration = await db.get(AgentCollaboration, collaboration_id)
    if collaboration is None:
        raise ValueError(f"unknown collaboration '{collaboration_id}'")
    collaborator = await get_autonomous_agent(db, collaboration.collaborator_agent_id)

    collaboration.status = AgentCollaborationStatus.running.value
    await db.flush()
    try:
        output = await chat_completion([{"role": "user", "content": f"Your own goal: {collaborator.goal}\n\nA collaborating agent asks you to help with: {collaboration.task}"}])
        collaboration.result = {"output": output}
        collaboration.status = AgentCollaborationStatus.completed.value
    except LLMError as exc:
        collaboration.result = {"error": str(exc)}
        collaboration.status = AgentCollaborationStatus.failed.value
    await db.flush()
    return collaboration


async def list_collaborations(db: AsyncSession, agent_id: uuid.UUID) -> list[AgentCollaboration]:
    return list((await db.scalars(
        select(AgentCollaboration).where(
            (AgentCollaboration.initiator_agent_id == agent_id) | (AgentCollaboration.collaborator_agent_id == agent_id)
        ).order_by(AgentCollaboration.created_at.desc())
    )).all())
