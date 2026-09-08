"""
Partie 7.1.1/7.1.2/7.1.6 -- real permission resolution shared by every
Evaluation Lab router. None of these literal endpoint paths carry
`{org_id}` beyond the top-level `POST/GET /organizations/{org_id}/datasets`
-- every other real route (`/datasets/{dataset_id}`,
`/datasets/{dataset_id}/questions`, `/questions/{question_id}`,
`/sets/{set_id}`, `/versions/{version_id}`) resolves the real resource
AND the caller's real organization role together, same "404, not 403,
for a non-member" anti-enumeration reasoning as
`api/security/agents.py`'s own `require_agent_member`.

**Admin+ throughout, not Manager+**: every one of these 6 étapes'
own literal endpoint list says "(Admin+)" -- Owner or Admin, the SAME
real tier `api/security/organizations.py`'s own `require_org_admin`
already enforces for `api/routers/usage.py`'s own org-level visibility
endpoints. Evaluation datasets are configuration/tooling for this
organization's OWN evaluation process, not a member-management
concern, same reasoning as usage."""

import uuid

from fastapi import Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from api.dependencies import get_current_user, get_db
from api.models.evaluation import BenchmarkVersion, EvaluationDataset, EvaluationQuestion, QuestionSet
from api.models.organization import OrganizationMember, OrganizationRole
from api.models.user import User

_NOT_FOUND = HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Not found")


async def _membership_for(organization_id: uuid.UUID, current_user: User, db: AsyncSession) -> OrganizationMember:
    membership = await db.scalar(
        select(OrganizationMember).where(
            OrganizationMember.organization_id == organization_id, OrganizationMember.user_id == current_user.id,
        )
    )
    if membership is None:
        raise _NOT_FOUND
    return membership


def _require_admin(membership: OrganizationMember) -> OrganizationMember:
    if membership.role not in (OrganizationRole.owner, OrganizationRole.admin):
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Organization admin access required")
    return membership


async def require_dataset_admin(
    dataset_id: uuid.UUID, current_user: User = Depends(get_current_user), db: AsyncSession = Depends(get_db),
) -> tuple[EvaluationDataset, OrganizationMember]:
    dataset = await db.get(EvaluationDataset, dataset_id)
    if dataset is None or dataset.deleted_at is not None:
        raise _NOT_FOUND
    membership = await _membership_for(dataset.organization_id, current_user, db)
    return dataset, _require_admin(membership)


async def require_question_admin(
    question_id: uuid.UUID, current_user: User = Depends(get_current_user), db: AsyncSession = Depends(get_db),
) -> tuple[EvaluationQuestion, OrganizationMember]:
    question = await db.get(EvaluationQuestion, question_id)
    if question is None:
        raise _NOT_FOUND
    dataset = await db.get(EvaluationDataset, question.dataset_id)
    if dataset is None or dataset.deleted_at is not None:
        raise _NOT_FOUND
    membership = await _membership_for(dataset.organization_id, current_user, db)
    return question, _require_admin(membership)


async def require_question_set_admin(
    set_id: uuid.UUID, current_user: User = Depends(get_current_user), db: AsyncSession = Depends(get_db),
) -> tuple[QuestionSet, OrganizationMember]:
    question_set = await db.get(QuestionSet, set_id)
    if question_set is None:
        raise _NOT_FOUND
    dataset = await db.get(EvaluationDataset, question_set.dataset_id)
    if dataset is None or dataset.deleted_at is not None:
        raise _NOT_FOUND
    membership = await _membership_for(dataset.organization_id, current_user, db)
    return question_set, _require_admin(membership)


async def require_benchmark_version_admin(
    version_id: uuid.UUID, current_user: User = Depends(get_current_user), db: AsyncSession = Depends(get_db),
) -> tuple[BenchmarkVersion, OrganizationMember]:
    version = await db.get(BenchmarkVersion, version_id)
    if version is None:
        raise _NOT_FOUND
    dataset = await db.get(EvaluationDataset, version.dataset_id)
    if dataset is None or dataset.deleted_at is not None:
        raise _NOT_FOUND
    membership = await _membership_for(dataset.organization_id, current_user, db)
    return version, _require_admin(membership)
