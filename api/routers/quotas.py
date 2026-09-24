"""
Partie 1.3.6 -- viewing and adjusting an organization's resource quotas.
GET is Admin+ (an Admin should be able to see how close to a limit their
organization is, same "Admin gets real visibility" spirit as Etape
1.2.3); PATCH is Owner-only -- raising or lowering a plan-level limit is
judged an organization-level decision, not a member-management one, the
same boundary api/security/organizations.py already draws for renaming/
deleting the organization itself.
"""

import uuid

from fastapi import APIRouter, Depends
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from api.dependencies import get_db
from api.models.organization import OrganizationMember
from api.models.organization_quota import OrganizationQuota
from api.schemas.quotas import OrganizationQuotaResponse, OrganizationQuotaUpdateRequest, QuotaDimensionEntry
from api.security.permissions import require_permission
from api.security.organizations import require_org_admin, require_org_owner
from api.security.quotas import create_default_quota, get_quota_limits, get_quota_usage

router = APIRouter(tags=["quotas"])

# Maps a response field name to (limits dict key, usage dict key) --
# the two dicts use the "max_*" / bare-name conventions of
# api/security/quotas.py's get_quota_limits/get_quota_usage respectively.
_DIMENSIONS = [
    ("users", "max_users"), ("workspaces", "max_workspaces"), ("teams", "max_teams"),
    ("documents", "max_documents"), ("storage_mb", "max_storage_mb"),
    ("requests_per_month", "max_requests_per_month"), ("requests_per_day", "max_requests_per_day"),
    ("api_calls", "max_api_calls"), ("agents", "max_agents"), ("kb_size_mb", "max_kb_size_mb"),
]


async def _to_response(org_id: uuid.UUID, db: AsyncSession) -> OrganizationQuotaResponse:
    limits = await get_quota_limits(db, org_id)
    usage = await get_quota_usage(db, org_id)
    return OrganizationQuotaResponse(
        organization_id=org_id,
        **{name: QuotaDimensionEntry(limit=limits[limit_key], used=usage.get(name)) for name, limit_key in _DIMENSIONS},
    )


@router.get("/organizations/{org_id}/quotas", response_model=OrganizationQuotaResponse)
async def get_organization_quotas(
    org_id: uuid.UUID, _caller: OrganizationMember = Depends(require_org_admin), db: AsyncSession = Depends(get_db),
):
    return await _to_response(org_id, db)


@router.patch("/organizations/{org_id}/quotas", response_model=OrganizationQuotaResponse)
async def update_organization_quotas(
    org_id: uuid.UUID, payload: OrganizationQuotaUpdateRequest,
    _caller: OrganizationMember = Depends(require_org_owner), db: AsyncSession = Depends(get_db),
):
    quota = await db.scalar(select(OrganizationQuota).where(OrganizationQuota.organization_id == org_id))
    if quota is None:
        # Every organization gets one at creation
        # (create_organization_with_owner) -- reaching this means the
        # org predates this step; create it now rather than 404ing an
        # Owner who's allowed to be here.
        quota = await create_default_quota(db, organization_id=org_id)

    for field, value in payload.model_dump(exclude_unset=True).items():
        setattr(quota, field, value)

    await db.commit()
    # _to_response re-queries fresh rather than reading attributes off
    # `quota` directly -- no explicit refresh needed here (contrast
    # api/routers/organizations.py's update_organization, which DOES
    # need one because it reads `updated_at` off the same in-memory
    # object right after commit).
    return await _to_response(org_id, db)
