"""
Hardening Mission (§14) -- HTTP surface of the Factory
(`api/services/agent_factory.py`):

- `POST /organizations/{org_id}/factory/blueprint` -- dry run: requirement ->
  blueprint + the list of validation problems (nothing is written).
- `POST /organizations/{org_id}/factory/deploy`    -- validate, create the real
  agent and, when a dataset is given, benchmark it and apply a measured gate.

Both need `agents:write`. Deploying with an evaluation runs real LLM-backed jobs,
so it shares the organization's evaluation-run rate limit and passes the same
credit / spend-cap pre-flight as every other paid entry point.
"""

import uuid

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel, Field
from sqlalchemy.ext.asyncio import AsyncSession

from api.config import settings
from api.dependencies import get_db
from api.models.organization import OrganizationMember
from api.security.organization_settings import get_org_settings
from api.security.permissions import require_permission
from api.security.rate_limit import enforce_rate_limit
from api.services.agent_factory import FactoryError, build_agent_blueprint, deploy_blueprint, validate_blueprint
from api.services.billing_credits import InsufficientCreditsError, SpendCapExceededError, assert_org_can_spend
from api.services.llm_config import resolve_llm_config

router = APIRouter(tags=["agent-factory"])


class BlueprintRequest(BaseModel):
    requirement: str = Field(min_length=10, max_length=4000)
    name: str | None = Field(default=None, max_length=200)


class BlueprintResponse(BaseModel):
    blueprint: dict
    problems: list[str]
    deployable: bool


class DeployRequest(BlueprintRequest):
    evaluate_dataset_id: uuid.UUID | None = None
    # With a dataset: the agent is held back (paused) unless `target_metric` averages at least this.
    min_target_value: float | None = Field(default=None, ge=0.0, le=1.0)
    target_metric: str = Field(default="recall_at_5", min_length=1, max_length=50)


class DeployResponse(BaseModel):
    agent_id: uuid.UUID
    status: str
    decision: str
    metrics: dict | None
    target_metric: str
    min_target_value: float | None
    blueprint: dict


@router.post("/organizations/{org_id}/factory/blueprint", response_model=BlueprintResponse)
async def factory_blueprint_endpoint(
    org_id: uuid.UUID, payload: BlueprintRequest, _caller: OrganizationMember = Depends(require_permission("agents:write")),
):
    try:
        blueprint = build_agent_blueprint(payload.requirement, payload.name)
    except FactoryError as exc:
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail=exc.problems) from exc
    problems = validate_blueprint(blueprint)
    return BlueprintResponse(blueprint=blueprint, problems=problems, deployable=not problems)


@router.post("/organizations/{org_id}/factory/deploy", response_model=DeployResponse, status_code=status.HTTP_201_CREATED)
async def factory_deploy_endpoint(
    org_id: uuid.UUID, payload: DeployRequest,
    caller: OrganizationMember = Depends(require_permission("agents:write")), db: AsyncSession = Depends(get_db),
):
    try:
        blueprint = build_agent_blueprint(payload.requirement, payload.name)
    except FactoryError as exc:
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail=exc.problems) from exc

    if payload.evaluate_dataset_id is not None:
        await enforce_rate_limit(
            f"ratelimit:evaluation_run:org:{org_id}", settings.EVALUATION_RUN_RATE_LIMIT_MAX_ATTEMPTS, settings.EVALUATION_RUN_RATE_LIMIT_WINDOW_SECONDS,
        )
        org_settings = await get_org_settings(db, org_id)
        try:
            await assert_org_can_spend(db, org_id, org_settings, resolve_llm_config(org_settings)["provider"])
        except InsufficientCreditsError as exc:
            raise HTTPException(status_code=status.HTTP_402_PAYMENT_REQUIRED, detail="Insufficient AI credits -- add a credit pack or configure your own provider key (BYOK)") from exc
        except SpendCapExceededError as exc:
            raise HTTPException(status_code=status.HTTP_429_TOO_MANY_REQUESTS, detail=f"Spend cap exceeded: {exc}") from exc

    try:
        result = await deploy_blueprint(
            db, org_id, blueprint, caller.user_id, payload.evaluate_dataset_id, payload.min_target_value, payload.target_metric,
        )
    except FactoryError as exc:
        await db.rollback()
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail=exc.problems) from exc
    await db.commit()
    return DeployResponse(**result)
