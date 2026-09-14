"""Partie 24 -- real, single-resource access dependencies for
`/fine-tuning/datasets/{id}`, `/fine-tuning/jobs/{id}`, and
`/fine-tuning/models/{id}` routes (flat paths, no `{org_id}` -- same
access-level adaptation already applied for Parties 19-23). Org-scoped
list/create routes reuse `require_org_member`/`require_org_admin`
directly."""

import uuid

from fastapi import Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from api.dependencies import get_current_user, get_db
from api.models.fine_tuning import FineTunedModel, FineTuningDataset, FineTuningJob
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


def _require_member_excluding_viewer(membership: OrganizationMember) -> OrganizationMember:
    if membership.role == OrganizationRole.viewer:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="This action is not available to Viewer members")
    return membership


def _require_admin(membership: OrganizationMember) -> OrganizationMember:
    if membership.role not in (OrganizationRole.owner, OrganizationRole.admin):
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Organization admin access required")
    return membership


async def require_dataset_member(dataset_id: uuid.UUID, current_user: User = Depends(get_current_user), db: AsyncSession = Depends(get_db)) -> tuple[FineTuningDataset, OrganizationMember]:
    dataset = await db.get(FineTuningDataset, dataset_id)
    if dataset is None:
        raise _NOT_FOUND
    return dataset, _require_member_excluding_viewer(await _membership_for(dataset.organization_id, current_user, db))


async def require_dataset_admin(dataset_id: uuid.UUID, current_user: User = Depends(get_current_user), db: AsyncSession = Depends(get_db)) -> tuple[FineTuningDataset, OrganizationMember]:
    dataset = await db.get(FineTuningDataset, dataset_id)
    if dataset is None:
        raise _NOT_FOUND
    return dataset, _require_admin(await _membership_for(dataset.organization_id, current_user, db))


async def require_job_member(job_id: uuid.UUID, current_user: User = Depends(get_current_user), db: AsyncSession = Depends(get_db)) -> tuple[FineTuningJob, OrganizationMember]:
    job = await db.get(FineTuningJob, job_id)
    if job is None:
        raise _NOT_FOUND
    return job, _require_member_excluding_viewer(await _membership_for(job.organization_id, current_user, db))


async def require_job_admin(job_id: uuid.UUID, current_user: User = Depends(get_current_user), db: AsyncSession = Depends(get_db)) -> tuple[FineTuningJob, OrganizationMember]:
    job = await db.get(FineTuningJob, job_id)
    if job is None:
        raise _NOT_FOUND
    return job, _require_admin(await _membership_for(job.organization_id, current_user, db))


async def require_model_member(model_id: uuid.UUID, current_user: User = Depends(get_current_user), db: AsyncSession = Depends(get_db)) -> tuple[FineTunedModel, OrganizationMember]:
    model = await db.get(FineTunedModel, model_id)
    if model is None:
        raise _NOT_FOUND
    return model, _require_member_excluding_viewer(await _membership_for(model.organization_id, current_user, db))


async def require_model_admin(model_id: uuid.UUID, current_user: User = Depends(get_current_user), db: AsyncSession = Depends(get_db)) -> tuple[FineTunedModel, OrganizationMember]:
    model = await db.get(FineTunedModel, model_id)
    if model is None:
        raise _NOT_FOUND
    return model, _require_admin(await _membership_for(model.organization_id, current_user, db))
