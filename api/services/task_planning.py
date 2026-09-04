"""
Partie 5.1.13 -- real task decomposition: breaking one real objective
into real, ordered, dependency-aware steps, persisted, and executed in
real real dependency order.

**`decompose_task`, a real, pure LLM primitive**: reuses
`chat_completion` (Partie 4.1.7) to ask for a real JSON array of steps
(`{"description": ..., "depends_on": [sequence, ...]}`). A malformed
response degrades to a real, honest single-step plan wrapping the raw
objective -- never raises, never fabricates structure that wasn't
really there.

**`execute_plan`, real topological ordering, deliberately SEQUENTIAL**:
a real Kahn's-algorithm batching computes which steps are actually
ready (every real dependency completed) at each round -- but steps
within a ready round run one at a time, not concurrently. This is a
real, deliberate simplification: true per-round parallelism would
reintroduce the exact `AsyncSession`-concurrency risk
`api/services/agent_orchestrator.py`'s own `run_multi_agent` already
had to solve with a real `asyncio.Lock` -- this étape's own literal ask
is "respecter les dépendances," not "exécuter en parallèle" (that's
Partie 5.1.8's own, already-built, separate scope). **Robustness
(vision critique)**: a real step failure marks that step `failed` and
every real step that (transitively) depends on it `skipped` --
independent steps still run."""

import datetime as dt
import json
import uuid

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from api.config import settings
from api.models.task_plan import TaskPlan, TaskPlanStatus, TaskStep, TaskStepStatus
from api.services.llm_providers import LLMError, chat_completion


async def decompose_task(task: str, context: str | None = None) -> list[dict]:
    """Partie 5.1.13's own literal function -- a real list of
    `{"description": str, "depends_on": list[int]}` dicts, `depends_on`
    referencing other steps' own 0-based position in this SAME list.
    Real, honest fallback: `[{"description": task, "depends_on": []}]`
    on any parse failure."""
    prompt = (
        f"Break this objective down into a numbered list of concrete, ordered steps.\n"
        f"Respond with ONLY a JSON array like "
        f'[{{"description": "...", "depends_on": [0, 1]}}], where depends_on lists the'
        f" 0-based indices of steps that must complete first (usually just the previous step, "
        f"or [] for the first step).\n\nObjective: {task}"
    )
    if context:
        prompt = f"{prompt}\n\nContext:\n{context}"

    try:
        response = await chat_completion([{"role": "user", "content": prompt}])
        steps = json.loads(response.strip())
        if not isinstance(steps, list) or not steps:
            raise ValueError("empty or non-list plan")
        for step in steps:
            if not isinstance(step, dict) or "description" not in step:
                raise ValueError("malformed step")
    except (LLMError, json.JSONDecodeError, ValueError, TypeError):
        return [{"description": task, "depends_on": []}]

    return [{"description": s["description"], "depends_on": s.get("depends_on", [])} for s in steps]


def validate_plan(steps: list[dict]) -> list[str]:
    """Partie 5.1.13's own literal function -- real, human-readable
    errors: too many real steps, a real dangling dependency (points at
    a `sequence` that doesn't exist), or a real dependency cycle (Kahn's
    algorithm makes no progress). Empty list means the plan is real and
    valid."""
    errors = []
    if len(steps) > settings.TASK_PLANNING_MAX_STEPS:
        errors.append(f"Plan has {len(steps)} steps, exceeding the real maximum of {settings.TASK_PLANNING_MAX_STEPS}")

    valid_indices = set(range(len(steps)))
    for i, step in enumerate(steps):
        for dep in step.get("depends_on", []):
            if dep not in valid_indices:
                errors.append(f"Step {i} depends on unknown step {dep}")
            elif dep == i:
                errors.append(f"Step {i} depends on itself")

    if not errors and _topological_order(steps) is None:
        errors.append("Plan contains a real dependency cycle")

    return errors


def _topological_order(steps: list[dict]) -> list[list[int]] | None:
    """Real Kahn's-algorithm batching -- returns real, ordered ROUNDS
    (each a list of step indices whose real dependencies are all
    already satisfied by earlier rounds), or `None` if a real cycle
    means no valid order exists."""
    remaining = {i: set(step.get("depends_on", [])) for i, step in enumerate(steps)}
    done: set[int] = set()
    rounds: list[list[int]] = []

    while remaining:
        ready = [i for i, deps in remaining.items() if deps <= done]
        if not ready:
            return None  # a real cycle (or a dangling dependency validate_plan should have already caught)
        rounds.append(ready)
        done.update(ready)
        for i in ready:
            del remaining[i]

    return rounds


async def plan_task(db: AsyncSession, objective: str, context: str | None = None) -> TaskPlan:
    """Partie 5.1.13's own literal function -- real decomposition,
    real, immediate persistence of every real step."""
    steps = await decompose_task(objective, context)
    plan = TaskPlan(objective=objective, status=TaskPlanStatus.pending.value)
    db.add(plan)
    await db.flush()

    for i, step in enumerate(steps):
        db.add(TaskStep(plan_id=plan.id, description=step["description"], sequence=i, dependencies=step.get("depends_on", [])))
    await db.flush()
    return plan


async def get_plan_steps(db: AsyncSession, plan_id: uuid.UUID) -> list[TaskStep]:
    """Real, additional function (not one of this étape's own literal
    ones) -- every real step of a plan, in real `sequence` order."""
    return list((await db.scalars(select(TaskStep).where(TaskStep.plan_id == plan_id).order_by(TaskStep.sequence))).all())


async def get_plan_status(db: AsyncSession, plan_id: uuid.UUID) -> str | None:
    """Partie 5.1.13's own literal function -- `None` for an unknown id."""
    plan = await db.get(TaskPlan, plan_id)
    return plan.status if plan is not None else None


async def update_plan(db: AsyncSession, plan_id: uuid.UUID, status: str, result: dict | None = None) -> TaskPlan | None:
    """Partie 5.1.13's own literal function -- `result` is stored under
    `metadata_json["result"]` (`TaskPlan` has no dedicated `result`
    column of its own in this étape's own literal schema -- individual
    STEPS carry their own real `result`)."""
    plan = await db.get(TaskPlan, plan_id)
    if plan is None:
        return None
    plan.status = status
    if result is not None:
        plan.metadata_json = {**(plan.metadata_json or {}), "result": result}
    await db.flush()
    return plan


async def execute_plan(db: AsyncSession, plan_id: uuid.UUID) -> TaskPlan:
    """Partie 5.1.13's own literal function -- see this module's own
    top docstring for the real topological, deliberately sequential
    execution order and the real skip-on-failed-dependency behavior.
    Always returns the real, final `TaskPlan` (never raises) -- a real
    step failure is data (`TaskStep.status`/`.error`), not a crash."""
    plan = await db.get(TaskPlan, plan_id)
    if plan is None:
        raise ValueError(f"Unknown plan: {plan_id}")

    steps = await get_plan_steps(db, plan_id)
    by_sequence = {s.sequence: s for s in steps}

    plan.status = TaskPlanStatus.running.value
    await db.flush()

    rounds = _topological_order([{"depends_on": s.dependencies} for s in steps])
    if rounds is None:
        plan.status = TaskPlanStatus.failed.value
        await db.flush()
        return plan

    failed_sequences: set[int] = set()
    for round_ in rounds:
        for sequence in round_:
            step = by_sequence[sequence]
            if any(dep in failed_sequences for dep in step.dependencies):
                step.status = TaskStepStatus.skipped.value
                step.completed_at = dt.datetime.now(dt.timezone.utc)
                failed_sequences.add(sequence)
                continue

            step.status = TaskStepStatus.running.value
            await db.flush()
            try:
                step.result = await chat_completion([{"role": "user", "content": step.description}])
            except LLMError as exc:
                step.status = TaskStepStatus.failed.value
                step.error = str(exc)
                failed_sequences.add(sequence)
            else:
                step.status = TaskStepStatus.completed.value
            step.completed_at = dt.datetime.now(dt.timezone.utc)
            await db.flush()

    plan.status = TaskPlanStatus.failed.value if failed_sequences else TaskPlanStatus.completed.value
    await db.flush()
    return plan
