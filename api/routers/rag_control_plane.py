"""
Real, explicitly-triggered orchestration endpoints -- Systèmes
internes, items 13 (OPA)/18 (RAG Evolution Engine)/20 (Canary)/27 (RAG
Control Plane). These tools are meant to be triggered by an operator/
admin (or a future real Celery schedule), never silently invoked on
every real user request -- same real distinction as
`api/routers/evaluation_jobs.py`'s own real, explicit job-creation
endpoints vs. the live `/search` path. `require_permission("evaluation:manage")`
matches this codebase's own real, existing 52-permission catalog
(`api/security/permission_catalog.py`) -- no new permission key
invented for this étape.
"""

import uuid

from fastapi import APIRouter, Depends, HTTPException, Request, status
from sqlalchemy.ext.asyncio import AsyncSession

from api.dependencies import get_db
from api.models.organization import OrganizationMember
from api.schemas.rag_control_plane import (
    ApplyRetrievalConfigRequest, ApplyRetrievalConfigResponse, CanaryEvaluationRequest, CanaryEvaluationResponse, EvolutionRunRequest,
    EvolutionRunResponse, HealthCheckResponse, MultiDatasetEvolutionResponse, RetrievalEvolutionRunRequest, RetrievalEvolutionRunResponse,
)
from api.security.permissions import require_permission

router = APIRouter(tags=["rag-control-plane"])


@router.post("/organizations/{org_id}/rag-control-plane/health-check", response_model=HealthCheckResponse)
async def run_health_check_endpoint(
    org_id: uuid.UUID, _caller: OrganizationMember = Depends(require_permission("evaluation:manage")),
    db: AsyncSession = Depends(get_db),
):
    """Item 27 -- real, consolidated report: every real, currently-
    running `ABTest` evaluated, plus this organization's own recent
    RAG Genome experiment history."""
    from api.services.rag_control_plane import run_health_check

    report = await run_health_check(db, org_id)
    await db.commit()
    return HealthCheckResponse(**report)


async def _require_dataset_in_org(db: AsyncSession, org_id: uuid.UUID, dataset_id: uuid.UUID) -> None:
    """Hardening Mission (§24) -- the evolution routes take `dataset_id`
    from the BODY while the caller was only authorized for `org_id` in the
    path: nothing checked they matched, so an Admin of organization A could
    launch (paid, LLM-backed) evaluation cycles on organization B's dataset
    and read its metrics back. Same 404 for "no such dataset" and "not yours"."""
    from api.models.evaluation import EvaluationDataset

    dataset = await db.get(EvaluationDataset, dataset_id)
    if dataset is None or dataset.organization_id != org_id:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Dataset not found")


async def _enforce_evolution_limits(db: AsyncSession, org_id: uuid.UUID) -> None:
    """An evolution cycle runs several full evaluation jobs (one LLM call per
    question each): it shares the organization's evaluation-run budget with
    `POST /datasets/{id}/evaluate` and the MCP `run_eval_benchmark` tool, and
    passes the same credit / spend-cap pre-flight as any other paid LLM entry."""
    from api.config import settings
    from api.security.organization_settings import get_org_settings
    from api.security.rate_limit import enforce_rate_limit
    from api.services.billing_credits import InsufficientCreditsError, SpendCapExceededError, assert_org_can_spend
    from api.services.llm_config import resolve_llm_config

    await enforce_rate_limit(f"ratelimit:evaluation_run:org:{org_id}", settings.EVALUATION_RUN_RATE_LIMIT_MAX_ATTEMPTS, settings.EVALUATION_RUN_RATE_LIMIT_WINDOW_SECONDS)
    org_settings = await get_org_settings(db, org_id)
    try:
        await assert_org_can_spend(db, org_id, org_settings, resolve_llm_config(org_settings)["provider"])
    except InsufficientCreditsError as exc:
        raise HTTPException(status_code=status.HTTP_402_PAYMENT_REQUIRED, detail="Insufficient AI credits -- add a credit pack or configure your own provider key (BYOK)") from exc
    except SpendCapExceededError as exc:
        raise HTTPException(status_code=status.HTTP_429_TOO_MANY_REQUESTS, detail=f"Spend cap exceeded: {exc}") from exc


@router.post("/organizations/{org_id}/evolution/run", response_model=EvolutionRunResponse)
async def run_evolution_endpoint(
    org_id: uuid.UUID, payload: EvolutionRunRequest,
    _caller: OrganizationMember = Depends(require_permission("evaluation:manage")), db: AsyncSession = Depends(get_db),
):
    """Item 18 -- real observe->diagnose->propose->experiment->measure->
    recommend cycle over one real evaluation dataset. Never applies its
    own real recommendation automatically -- see
    `api.services.rag_evolution_engine.run_evolution_cycle`'s own
    module docstring."""
    from api.services.rag_evolution_engine import run_evolution_cycle

    await _require_dataset_in_org(db, org_id, payload.dataset_id)
    await _enforce_evolution_limits(db, org_id)
    result = await run_evolution_cycle(db, payload.dataset_id, payload.llm_provider, payload.llm_model, payload.target_metric)
    await db.commit()
    return EvolutionRunResponse(
        baseline_job_id=result["baseline_job_id"], candidate_job_id=result.get("candidate_job_id"),
        decision=result["decision"], reason=result.get("reason"), target_metric=result.get("target_metric"),
        target_metric_delta=result.get("target_metric_delta"), candidate_system_prompt=result.get("candidate_system_prompt"),
    )


@router.post("/organizations/{org_id}/evolution/retrieval/run-multi", response_model=MultiDatasetEvolutionResponse)
async def run_multi_dataset_evolution_endpoint(
    org_id: uuid.UUID, payload: RetrievalEvolutionRunRequest,
    _caller: OrganizationMember = Depends(require_permission("evaluation:manage")), db: AsyncSession = Depends(get_db),
):
    """Same as `.../retrieval/run`, but over `dataset_id` + `extra_dataset_ids`: a candidate is recommended only if it is
    accepted on EVERY dataset (guards against a setting overfitted to one question set). Costs one full cycle per dataset,
    so the evaluation rate-limit budget is charged once per dataset."""
    from api.services.agent_knowledge_base import AgentKnowledgeBaseError
    from api.services.rag_evolution_engine import run_multi_dataset_retrieval_evolution

    dataset_ids = list(dict.fromkeys([payload.dataset_id, *payload.extra_dataset_ids]))
    for dataset_id in dataset_ids:
        await _require_dataset_in_org(db, org_id, dataset_id)
    for _ in dataset_ids:
        await _enforce_evolution_limits(db, org_id)
    try:
        result = await run_multi_dataset_retrieval_evolution(
            db, dataset_ids, payload.candidates, payload.target_metric, payload.min_improvement, payload.max_regression,
        )
    except AgentKnowledgeBaseError as exc:
        await db.rollback()
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc
    return MultiDatasetEvolutionResponse(**{**result, "per_dataset": [{**d, "dataset_id": str(d["dataset_id"]), "baseline_job_id": str(d["baseline_job_id"])} for d in result["per_dataset"]]})


@router.post("/organizations/{org_id}/evolution/retrieval/run", response_model=RetrievalEvolutionRunResponse)
async def run_retrieval_evolution_endpoint(
    org_id: uuid.UUID, payload: RetrievalEvolutionRunRequest,
    _caller: OrganizationMember = Depends(require_permission("evaluation:manage")), db: AsyncSession = Depends(get_db),
):
    """Multi-candidate retrieval-configuration search with a minimum-gain
    threshold and a no-regression guard (see
    `api.services.rag_evolution_engine.run_retrieval_evolution_cycle`).
    Recommends, never applies."""
    from api.services.agent_knowledge_base import AgentKnowledgeBaseError
    from api.services.rag_evolution_engine import run_retrieval_evolution_cycle

    await _require_dataset_in_org(db, org_id, payload.dataset_id)
    await _enforce_evolution_limits(db, org_id)
    try:
        result = await run_retrieval_evolution_cycle(
            db, payload.dataset_id, payload.candidates, payload.target_metric, payload.min_improvement, payload.max_regression,
        )
    except AgentKnowledgeBaseError as exc:
        await db.rollback()
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc
    return RetrievalEvolutionRunResponse(**result)


@router.post("/organizations/{org_id}/agents/{agent_id}/retrieval-config/apply", response_model=ApplyRetrievalConfigResponse)
async def apply_retrieval_config_endpoint(
    org_id: uuid.UUID, agent_id: uuid.UUID, payload: ApplyRetrievalConfigRequest, request: Request,
    caller: OrganizationMember = Depends(require_permission("evaluation:manage")), db: AsyncSession = Depends(get_db),
):
    """The explicit, human-triggered APPLY step for an evolution
    recommendation. Returns the previous config; rolling back is this same
    call with `config=previous, replace=true`. Audit-logged."""
    from api.models.audit_log import AuditAction
    from api.security.audit_log import log_audit_action
    from api.services.agent_knowledge_base import AgentKnowledgeBaseError
    from api.services.rag_evolution_engine import apply_retrieval_recommendation
    from api.utils import client_ip

    try:
        result = await apply_retrieval_recommendation(db, org_id, agent_id, payload.config, payload.replace)
    except AgentKnowledgeBaseError as exc:
        await db.rollback()
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc
    except ValueError as exc:
        await db.rollback()
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Agent not found") from exc
    await log_audit_action(
        db, user_id=caller.user_id, action=AuditAction.AGENT_UPDATED, ip=client_ip(request), user_agent=request.headers.get("user-agent"),
        success=True, organization_id=org_id, resource_type="agent_retrieval_config", resource_id=str(agent_id),
        metadata={"previous": result["previous"], "current": result["current"], "replace": payload.replace},
    )
    await db.commit()
    return ApplyRetrievalConfigResponse(**result)


@router.post("/organizations/{org_id}/ab-tests/{test_id}/evaluate-canary", response_model=CanaryEvaluationResponse)
async def evaluate_canary_endpoint(
    org_id: uuid.UUID, test_id: uuid.UUID, payload: CanaryEvaluationRequest,
    _caller: OrganizationMember = Depends(require_permission("evaluation:manage")), db: AsyncSession = Depends(get_db),
):
    """Item 20 -- real, one-shot canary health check. Rollback
    (pausing the real `ABTest`) is auto-executed on a real, significant
    regression; promotion is only ever recommended -- see
    `api.services.canary_rollout.evaluate_canary`'s own module
    docstring for the real, deliberately asymmetric reasoning."""
    from api.models.evaluation import ABTest
    from api.services.canary_rollout import evaluate_canary

    test = await db.get(ABTest, test_id)
    if test is None or test.organization_id != org_id:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="AB test not found")

    result = await evaluate_canary(db, test_id, payload.target_metric, payload.regression_threshold)
    await db.commit()
    return CanaryEvaluationResponse(
        test_id=result["test_id"], action=result["action"], reason=result["reason"],
        metric_result=result.get("metric_result"), recommended_traffic_split=result.get("recommended_traffic_split"),
    )
