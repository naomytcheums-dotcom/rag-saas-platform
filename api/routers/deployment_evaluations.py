"""Partie 7.3.8 -- auto-eval before deployment endpoints. Manager+
(Owner/Admin/Manager) throughout, matching this étape's own literal
ask -- a real, lower tier than every other Evaluation Lab endpoint's
own Admin+ (deployment gating is closer to real agent operations,
`api/security/agents.py`'s own `require_agent_manager` tier, than to
org-level evaluation tooling configuration)."""

from fastapi import APIRouter, Depends, status
from sqlalchemy.ext.asyncio import AsyncSession

from api.dependencies import get_current_user, get_db
from api.models.agent import Agent
from api.models.evaluation import DeploymentEvaluation
from api.models.organization import OrganizationMember
from api.models.user import User
from api.schemas.evaluation import (
    DeployAgentResponse, DeploymentEvaluationCreateRequest, DeploymentEvaluationListResponse, DeploymentEvaluationResponse,
)
from api.security.agents import require_agent_manager
from api.security.evaluation import require_deployment_evaluation_manager
from api.services.deployment_evaluations import (
    create_deployment_evaluation, deploy_agent, list_deployment_evaluations, pass_deployment_evaluation,
    schedule_deployment_evaluation_processing,
)

router = APIRouter(tags=["deployment-evaluations"])


@router.post("/agents/{agent_id}/deploy/evaluate", response_model=DeploymentEvaluationResponse, status_code=status.HTTP_201_CREATED)
async def create_deployment_evaluation_endpoint(
    payload: DeploymentEvaluationCreateRequest, agent_ctx: tuple[Agent, OrganizationMember] = Depends(require_agent_manager),
    current_user: User = Depends(get_current_user), db: AsyncSession = Depends(get_db),
):
    agent, _caller = agent_ctx
    evaluation = await create_deployment_evaluation(db, agent.id, payload.dataset_id, payload.version, payload.thresholds, current_user.id)
    await db.commit()
    await db.refresh(evaluation)
    schedule_deployment_evaluation_processing(evaluation.id)
    return evaluation


@router.get("/agents/{agent_id}/deploy/evaluations", response_model=DeploymentEvaluationListResponse)
async def list_deployment_evaluations_endpoint(agent_ctx: tuple[Agent, OrganizationMember] = Depends(require_agent_manager), db: AsyncSession = Depends(get_db)):
    agent, _caller = agent_ctx
    return await list_deployment_evaluations(db, agent.id)


@router.get("/deploy/evaluations/{evaluation_id}", response_model=DeploymentEvaluationResponse)
async def get_deployment_evaluation_endpoint(evaluation_ctx: tuple[DeploymentEvaluation, OrganizationMember] = Depends(require_deployment_evaluation_manager)):
    evaluation, _caller = evaluation_ctx
    return evaluation


@router.post("/deploy/evaluations/{evaluation_id}/pass", response_model=DeploymentEvaluationResponse)
async def pass_deployment_evaluation_endpoint(
    evaluation_ctx: tuple[DeploymentEvaluation, OrganizationMember] = Depends(require_deployment_evaluation_manager), db: AsyncSession = Depends(get_db),
):
    evaluation, _caller = evaluation_ctx
    updated = await pass_deployment_evaluation(db, evaluation.id)
    await db.commit()
    await db.refresh(updated)
    return updated


@router.post("/agents/{agent_id}/deploy", response_model=DeployAgentResponse)
async def deploy_agent_endpoint(agent_ctx: tuple[Agent, OrganizationMember] = Depends(require_agent_manager), db: AsyncSession = Depends(get_db)):
    agent, _caller = agent_ctx
    return await deploy_agent(db, agent.id)
