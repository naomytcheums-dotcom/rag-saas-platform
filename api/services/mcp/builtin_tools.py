"""
4 real MCP tools backing the `agents.md` contract (Factory / Autopsy / ChangeLab / benchmark).

These are the 4 named tools in `agents.md`'s own section 3 (MCP
Interface):
- `create_rag_agent`         (Mode 1 FACTORY)
- `get_failure_report`       (Mode 3 AUTOPSY)
- `update_retrieval_config`  (Mode 4 CHANGELAB)
- `run_eval_benchmark`       (Mode 2 GUARDIAN + Mode 4)

Each one wraps a REAL, existing service function — no duplicated logic,
no new engine.

Exposed by `api/routers/mcp_server.py`, so an external MCP client
can list them via `GET /mcp/v1/tools` and call them via
`POST /mcp/v1/tools/{name}/call`.
"""

from __future__ import annotations

import uuid
from typing import Any

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from api.models.agent import Agent


class MCPBuiltinToolError(Exception):
    """Real, honest error -- the MCP caller gets `is_error: true`, never
    a leaked 500."""


# ---------------------------------------------------------------------------
# Tool 1: create_rag_agent (Mode 1 FACTORY)
# ---------------------------------------------------------------------------


async def create_rag_agent(
    db: AsyncSession,
    organization_id: uuid.UUID,
    *,
    name: str | None = None,
    model: str | None = None,
    system_prompt: str | None = None,
    retrieval_config: dict[str, Any] | None = None,
    created_by: uuid.UUID | None = None,
) -> dict[str, Any]:
    """Mode 1 (FACTORY) — provision a real RAG agent.

    Delegates to the real `Agent` model. `retrieval_config` is VALIDATED
    (`validate_retrieval_config`: unknown keys, bad strategy, out-of-range
    top_k/score_threshold are rejected -- Hardening Mission §14, never a
    decorative JSON blob) and stored on the agent's own real
    `knowledge_base_config` column, which the Eval Lab now genuinely
    applies when benchmarking this agent
    (`api/services/evaluation_results.py::run_evaluation`).

    Returns `{"agent_id": ..., "status": "created"}`.
    """
    from api.services.agent_knowledge_base import AgentKnowledgeBaseError, validate_retrieval_config

    if not name or not name.strip():
        raise MCPBuiltinToolError("create_rag_agent: name is required")
    try:
        validated_config = validate_retrieval_config(retrieval_config or {})
    except AgentKnowledgeBaseError as exc:
        raise MCPBuiltinToolError(f"create_rag_agent: {exc}") from exc

    agent = Agent(
        organization_id=organization_id,
        name=name.strip(),
        model_config_json={"model": model or "claude-sonnet-5-5"},
        system_prompt=system_prompt or "You are a helpful assistant.",
        knowledge_base_config=validated_config,
        created_by=created_by,
    )
    db.add(agent)
    await db.flush()
    return {"agent_id": str(agent.id), "status": "created"}


# ---------------------------------------------------------------------------
# Tool 2: get_failure_report (Mode 3 AUTOPSY)
# ---------------------------------------------------------------------------


async def get_failure_report(
    db: AsyncSession,
    organization_id: uuid.UUID,
    *,
    run_id: uuid.UUID,
) -> dict[str, Any]:
    """Mode 3 (AUTOPSY) — categorize a real evaluation run's failures.

    Hardening Mission (§10/§24) -- two real bugs fixed here: (1) the run
    was never checked against `organization_id`, so any caller could read
    ANOTHER organization's failure report by guessing a job id (IDOR);
    an unknown run and another tenant's run now both raise the same
    "not found". (2) `question`/`expected`/`actual` were read via
    `getattr(f, "question", "")` from attributes `EvaluationFailure`
    never had, so every report returned empty strings -- they now come
    from the real joined `EvaluationQuestion` (`question`,
    `expected_answer`) and the real recorded `EvaluationFailure.error`.
    `categories` reuses `categorize_job_failures` (retrieval / generation
    / other from real failure rows, plus hallucination from the real,
    already-computed `hallucination_rate` metric) instead of a second,
    divergent tally.

    Returns `{"failures": [...], "categories": {...}}`.
    """
    from api.models.evaluation import EvaluationDataset, EvaluationFailure, EvaluationJob, EvaluationQuestion
    from api.services.evaluation_jobs import categorize_job_failures

    owned = await db.scalar(
        select(EvaluationJob.id)
        .join(EvaluationDataset, EvaluationDataset.id == EvaluationJob.dataset_id)
        .where(EvaluationJob.id == run_id, EvaluationDataset.organization_id == organization_id)
    )
    if owned is None:
        raise MCPBuiltinToolError(f"Run not found: {run_id}")

    rows = (
        await db.execute(
            select(EvaluationFailure, EvaluationQuestion)
            .join(EvaluationQuestion, EvaluationQuestion.id == EvaluationFailure.question_id)
            .where(EvaluationFailure.evaluation_job_id == run_id)
            .order_by(EvaluationFailure.created_at)
        )
    ).all()
    items = [
        {"question": q.question, "category": f.category, "expected": q.expected_answer or "", "actual": f.error}
        for f, q in rows
    ]
    return {"failures": items, "categories": await categorize_job_failures(db, run_id)}


# ---------------------------------------------------------------------------
# Tool 3: update_retrieval_config (Mode 4 CHANGELAB)
# ---------------------------------------------------------------------------


async def update_retrieval_config(
    db: AsyncSession,
    organization_id: uuid.UUID,
    *,
    agent_id: uuid.UUID,
    config: dict[str, Any],
) -> dict[str, Any]:
    """Mode 4 (CHANGELAB) — update a real agent's retrieval_config.

    Only updates the given keys (real partial merge, never a full
    replacement) so a targeted fix (e.g. bumping `top_k` from 5 to 10)
    does not silently wipe every other key. The change is VALIDATED
    (unknown keys / out-of-range values are rejected, §11) and is
    genuinely measurable: the Eval Lab applies the agent's stored config
    when benchmarking it, so a following `run_eval_benchmark` really
    exercises the new value.

    Returns `{"status": "updated", "updated_keys": [...]}`.
    """
    from api.services.agent_knowledge_base import AgentKnowledgeBaseError, validate_retrieval_config

    if not isinstance(config, dict) or not config:
        raise MCPBuiltinToolError("update_retrieval_config: config must be a non-empty object")
    try:
        validated = validate_retrieval_config(config)
    except AgentKnowledgeBaseError as exc:
        raise MCPBuiltinToolError(f"update_retrieval_config: {exc}") from exc

    agent = await db.scalar(
        select(Agent).where(
            Agent.id == agent_id,
            Agent.organization_id == organization_id,
        )
    )
    if agent is None:
        raise MCPBuiltinToolError(f"Agent not found: {agent_id}")

    merged = dict(agent.knowledge_base_config or {})
    merged.update(validated)
    agent.knowledge_base_config = merged
    await db.flush()
    return {"status": "updated", "updated_keys": sorted(validated.keys())}


# ---------------------------------------------------------------------------
# Tool 4: run_eval_benchmark (Mode 2 GUARDIAN + Mode 4)
# ---------------------------------------------------------------------------


async def run_eval_benchmark(
    db: AsyncSession,
    organization_id: uuid.UUID,
    *,
    dataset_id: uuid.UUID,
    agent_id: uuid.UUID | None = None,
    config: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """Mode 2 (GUARDIAN) + Mode 4 (CHANGELAB) — launch a real benchmark.

    Delegates to the real `evaluation_jobs` service (same code path the
    REST `/datasets/{id}/evaluate` endpoint uses). Executes the job
    synchronously so the caller gets real results in the same call (a
    queued Celery worker is not available on every deployment).

    Hardening Mission (§16/§24) -- the dataset (and agent, when given)
    must belong to `organization_id`: before this, any caller could run
    a benchmark on another tenant's dataset. Returns the job's real
    per-metric AVERAGES (`metrics`) computed from its persisted
    `EvaluationResult` rows, not just the bare result-id list.
    """
    from api.models.evaluation import EvaluationDataset
    from api.services.evaluation_jobs import create_evaluation_job, run_evaluation_job

    dataset = await db.get(EvaluationDataset, dataset_id)
    if dataset is None or dataset.organization_id != organization_id:
        raise MCPBuiltinToolError(f"Dataset not found: {dataset_id}")
    if agent_id is not None:
        owned_agent = await db.scalar(select(Agent.id).where(Agent.id == agent_id, Agent.organization_id == organization_id))
        if owned_agent is None:
            raise MCPBuiltinToolError(f"Agent not found: {agent_id}")

    job = await create_evaluation_job(
        db,
        dataset_id=dataset_id,
        agent_id=agent_id,
        model_config=config or None,
    )
    await db.flush()

    await run_evaluation_job(db, job.id)
    await db.refresh(job)

    return {
        "run_id": str(job.id),
        "status": job.status,
        "progress": job.progress,
        "total_questions": job.total_questions,
        "completed_questions": job.completed_questions,
        "metrics": await _job_metric_averages(db, job.id),
        "summary": job.results if job.results else None,
    }


async def _job_metric_averages(db: AsyncSession, job_id: uuid.UUID) -> dict[str, float]:
    """Real per-metric mean over every numeric top-level value in the
    job's persisted `EvaluationResult.metrics` rows (never fabricated:
    a metric no result computed is simply absent)."""
    from api.models.evaluation import EvaluationResult

    totals: dict[str, list[float]] = {}
    for metrics in (await db.scalars(select(EvaluationResult.metrics).where(EvaluationResult.evaluation_job_id == job_id))).all():
        for key, value in (metrics or {}).items():
            if isinstance(value, (int, float)) and not isinstance(value, bool):
                totals.setdefault(key, []).append(float(value))
    return {key: sum(values) / len(values) for key, values in sorted(totals.items())}


# ---------------------------------------------------------------------------
# Registry — name -> (handler, description, input_schema)
# ---------------------------------------------------------------------------


BUILTIN_TOOLS: dict[str, dict[str, Any]] = {
    "create_rag_agent": {
        "description": "Mode 1 (FACTORY) — provision a real RAG agent for an organization.",
        "input_schema": {
            "type": "object",
            "properties": {
                "organization_id": {"type": "string"},
                "name": {"type": "string"},
                "model": {"type": "string"},
                "system_prompt": {"type": "string"},
                "retrieval_config": {"type": "object"},
            },
            "required": ["organization_id", "name"],
        },
        "handler": create_rag_agent,
    },
    "get_failure_report": {
        "description": "Mode 3 (AUTOPSY) — categorize a real evaluation run's failures by category.",
        "input_schema": {
            "type": "object",
            "properties": {
                "organization_id": {"type": "string"},
                "run_id": {"type": "string"},
            },
            "required": ["organization_id", "run_id"],
        },
        "handler": get_failure_report,
    },
    "update_retrieval_config": {
        "description": "Mode 4 (CHANGELAB) — partial-update an agent's retrieval_config.",
        "input_schema": {
            "type": "object",
            "properties": {
                "organization_id": {"type": "string"},
                "agent_id": {"type": "string"},
                "config": {"type": "object"},
            },
            "required": ["organization_id", "agent_id", "config"],
        },
        "handler": update_retrieval_config,
    },
    "run_eval_benchmark": {
        "description": "Mode 2 (GUARDIAN) + Mode 4 (CHANGELAB) — launch a real benchmark run.",
        "input_schema": {
            "type": "object",
            "properties": {
                "organization_id": {"type": "string"},
                "dataset_id": {"type": "string"},
                "agent_id": {"type": "string"},
                "config": {"type": "object"},
            },
            "required": ["organization_id", "dataset_id"],
        },
        "handler": run_eval_benchmark,
    },
}


def list_builtin_tools() -> list[dict[str, Any]]:
    """Returns the 4 tools in MCP `tools/list` shape."""
    return [
        {
            "name": name,
            "description": spec["description"],
            "input_schema": spec["input_schema"],
        }
        for name, spec in BUILTIN_TOOLS.items()
    ]


def get_builtin_tool(name: str) -> dict[str, Any] | None:
    return BUILTIN_TOOLS.get(name)


async def call_builtin_tool(
    db: AsyncSession,
    name: str,
    payload: dict[str, Any],
) -> dict[str, Any]:
    """Call a builtin tool. Returns MCP `tools/call` shape:
    `{"content": [{"type": "text", "text": ...}], "is_error": bool}`.
    """
    import json

    spec = BUILTIN_TOOLS.get(name)
    if spec is None:
        return {
            "content": [{"type": "text", "text": f"Unknown builtin tool: {name!r}"}],
            "is_error": True,
        }

    args = dict(payload.get("arguments", payload)) if isinstance(payload, dict) else {}
    for key in ("organization_id", "agent_id", "dataset_id", "run_id"):
        if isinstance(args.get(key), str):
            try:
                args[key] = uuid.UUID(args[key])
            except (ValueError, TypeError):
                return {
                    "content": [{"type": "text", "text": f"Invalid {key}: {args[key]!r}"}],
                    "is_error": True,
                }

    try:
        result = await spec["handler"](db, **args)
    except MCPBuiltinToolError as exc:
        return {"content": [{"type": "text", "text": str(exc)}], "is_error": True}
    except Exception as exc:  # noqa: BLE001
        return {
            "content": [{"type": "text", "text": f"Tool execution failed: {exc}"}],
            "is_error": True,
        }

    return {
        "content": [{"type": "text", "text": json.dumps(result, default=str)}],
        "is_error": False,
    }
