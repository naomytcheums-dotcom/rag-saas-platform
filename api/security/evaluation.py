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
from api.models.evaluation import BenchmarkVersion, EvaluationDataset, EvaluationJob, EvaluationQuestion, ManualEvaluation, QuestionSet
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


def _require_member_excluding_viewer(membership: OrganizationMember) -> OrganizationMember:
    """Partie 7.3.2's own literal "Member+" tier -- same real
    exclusion as `api/security/organizations.py`'s own
    `require_org_member_excluding_viewer`, applied here since Manual
    evaluation's own routes are resolved by `question_id`/`evaluation_id`,
    not a top-level `{org_id}` path param that dependency itself needs."""
    if membership.role == OrganizationRole.viewer:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="This action is not available to Viewer members")
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


async def require_evaluation_job_admin(
    job_id: uuid.UUID, current_user: User = Depends(get_current_user), db: AsyncSession = Depends(get_db),
) -> tuple[EvaluationJob, OrganizationMember]:
    """Partie 7.3.1."""
    job = await db.get(EvaluationJob, job_id)
    if job is None:
        raise _NOT_FOUND
    dataset = await db.get(EvaluationDataset, job.dataset_id)
    if dataset is None or dataset.deleted_at is not None:
        raise _NOT_FOUND
    membership = await _membership_for(dataset.organization_id, current_user, db)
    return job, _require_admin(membership)


async def require_question_member(
    question_id: uuid.UUID, current_user: User = Depends(get_current_user), db: AsyncSession = Depends(get_db),
) -> tuple[EvaluationQuestion, OrganizationMember]:
    """Partie 7.3.2 -- same real resolution shape as
    `require_question_admin`, but the real, lower "Member+, excluding
    Viewer" tier this étape's own literal ask requires (a manual score
    is real, subjective FEEDBACK any real contributing member can
    leave, not org-level tooling configuration)."""
    question = await db.get(EvaluationQuestion, question_id)
    if question is None:
        raise _NOT_FOUND
    dataset = await db.get(EvaluationDataset, question.dataset_id)
    if dataset is None or dataset.deleted_at is not None:
        raise _NOT_FOUND
    membership = await _membership_for(dataset.organization_id, current_user, db)
    return question, _require_member_excluding_viewer(membership)


async def require_manual_evaluation_access(
    evaluation_id: uuid.UUID, current_user: User = Depends(get_current_user), db: AsyncSession = Depends(get_db),
) -> tuple[ManualEvaluation, OrganizationMember]:
    """Partie 7.3.2 -- resolves a real `ManualEvaluation` row and the
    caller's real Member+ role together; `PATCH /evaluations/{id}`'s
    own literal "Member+ si propriétaire" additionally checks real
    OWNERSHIP (`evaluation.evaluator_id == current_user.id`) OR real
    Admin+, one real layer up, in the router itself -- this dependency
    only resolves the real resource + base real membership, the same
    real split every other dependency in this module already uses."""
    evaluation = await db.get(ManualEvaluation, evaluation_id)
    if evaluation is None:
        raise _NOT_FOUND
    question = await db.get(EvaluationQuestion, evaluation.question_id)
    if question is None:
        raise _NOT_FOUND
    dataset = await db.get(EvaluationDataset, question.dataset_id)
    if dataset is None or dataset.deleted_at is not None:
        raise _NOT_FOUND
    membership = await _membership_for(dataset.organization_id, current_user, db)
    return evaluation, _require_member_excluding_viewer(membership)
