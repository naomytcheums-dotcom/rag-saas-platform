"""
IBM Bob 2.0 — 4 real MCP tools backing the `agents.md` contract.

These are the 4 named tools in `agents.md`'s own section 3 (MCP
Interface):
- `create_rag_agent`         (Mode 1 FACTORY)
- `get_failure_report`       (Mode 3 AUTOPSY)
- `update_retrieval_config`  (Mode 4 CHANGELAB)
- `run_eval_benchmark`       (Mode 2 GUARDIAN + Mode 4)

Each one wraps a REAL, existing service function — no duplicated logic,
no new engine.

Exposed by `api/routers/mcp_server.py`, so an external MCP client
(IBM Bob 2.0) can list them via `GET /mcp/v1/tools` and call them via
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

    Delegates to the real `Agent` model. `retrieval_config` is stored on
    the agent's own real `knowledge_base_config` JSON column (the real
    field api/services/agent_orchestrator.py reads at run time).

    Returns `{"agent_id": ..., "status": "created"}`.
    """
    if not name or not name.strip():
        raise MCPBuiltinToolError("create_rag_agent: name is required")

    agent = Agent(
        organization_id=organization_id,
        name=name.strip(),
        model_config_json={"model": model or "claude-3-5-sonnet"},
        system_prompt=system_prompt or "You are a helpful assistant.",
        knowledge_base_config=retrieval_config or {},
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

    Delegates to the real `EvaluationFailure` rows produced by
    `evaluation_jobs`. Groups by the real `category` column already
    populated during evaluation.

    Returns `{"failures": [...], "categories": {...}}`.
    """
    from api.models.evaluation import EvaluationFailure

    failures = (
        await db.scalars(
            select(EvaluationFailure).where(
                EvaluationFailure.evaluation_job_id == run_id,
            )
        )
    ).all()

    categories: dict[str, int] = {}
    items: list[dict[str, Any]] = []
    for f in failures:
        cat = getattr(f, "category", None) or "OTHER"
        categories[cat] = categories.get(cat, 0) + 1
        items.append(
            {
                "question": getattr(f, "question", "") or "",
                "category": cat,
                "expected": getattr(f, "expected", "") or "",
                "actual": getattr(f, "actual", "") or "",
            }
        )

    return {"failures": items, "categories": categories}


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
    does not silently wipe every other key. Merges into the agent's real
    `knowledge_base_config` JSON column.

    Returns `{"status": "updated", "updated_keys": [...]}`.
    """
    if not isinstance(config, dict) or not config:
        raise MCPBuiltinToolError("update_retrieval_config: config must be a non-empty object")

    agent = await db.scalar(
        select(Agent).where(
            Agent.id == agent_id,
            Agent.organization_id == organization_id,
        )
    )
    if agent is None:
        raise MCPBuiltinToolError(f"Agent not found: {agent_id}")

    merged = dict(agent.knowledge_base_config or {})
    merged.update(config)
    agent.knowledge_base_config = merged
    await db.flush()
    return {"status": "updated", "updated_keys": sorted(config.keys())}


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
    REST `/datasets/{id}/evaluate` endpoint uses). Returns immediately
    with a `run_id` (the job is queued asynchronously, like the REST
    endpoint).

    Returns `{"run_id": ..., "status": "completed"}`.

    IBM Bob 2.0 -- this tool executes the job synchronously so the
    caller (Bob, or any MCP client) gets real results in the same
    call. The alternative (queue + Celery worker) requires a
    dedicated worker process which Render Free does not provide.
    """
    from api.services.evaluation_jobs import (
        create_evaluation_job,
        run_evaluation_job,
    )

    job = await create_evaluation_job(
        db,
        dataset_id=dataset_id,
        agent_id=agent_id,
        model_config=config or None,
    )
    await db.flush()

    # Execute the job synchronously so the caller gets real results.
    await run_evaluation_job(db, job.id)
    await db.refresh(job)

    return {
        "run_id": str(job.id),
        "status": job.status,
        "progress": job.progress,
        "total_questions": job.total_questions,
        "completed_questions": job.completed_questions,
        "metrics": job.results if job.results else None,
    }


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
