"""
Partie 1.3.9 -- viewing and adjusting an organization's configuration.
GET is Admin+ (same tier as api/routers/quotas.py's GET -- an Admin
should be able to see how the organization is configured); PATCH is
Owner-only, same boundary as quotas' PATCH: changing what model/prompt/
retrieval strategy the whole organization uses is judged an
organization-level decision, not a member-management one.
"""

import uuid

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

from api.dependencies import get_db
from api.models.organization import OrganizationMember
from api.schemas.llm_byok import LLMConfigResponse, LLMConfigSetRequest
from api.schemas.organization_settings import OrganizationSettingsResponse, OrganizationSettingsUpdateRequest
from api.security.permissions import require_permission
from api.security.organizations import require_org_admin, require_org_owner
from api.security.organization_settings import get_org_settings, update_org_settings
from api.services.llm_byok import UnknownLLMProviderError, delete_org_llm_config, list_org_llm_configs, set_org_llm_config

router = APIRouter(tags=["organization-settings"])


@router.get("/organizations/{org_id}/settings", response_model=OrganizationSettingsResponse)
async def get_organization_settings(
    org_id: uuid.UUID, _caller: OrganizationMember = Depends(require_permission("settings:manage")), db: AsyncSession = Depends(get_db),
):
    settings = await get_org_settings(db, org_id)
    return OrganizationSettingsResponse(organization_id=org_id, **settings)


@router.patch("/organizations/{org_id}/settings", response_model=OrganizationSettingsResponse)
async def update_organization_settings(
    org_id: uuid.UUID, payload: OrganizationSettingsUpdateRequest,
    _caller: OrganizationMember = Depends(require_permission("settings:manage")), db: AsyncSession = Depends(get_db),
):
    updates = payload.model_dump(exclude_unset=True)

    # Cross-field validation the per-field Field() bounds in
    # OrganizationSettingsUpdateRequest can't express on their own: a
    # PATCH may touch only one of the two (or neither), so it's checked
    # against the RESULTING effective pair, not the raw payload.
    current = await get_org_settings(db, org_id)
    merged_preview = {**current, **updates}
    if merged_preview["chunk_overlap"] >= merged_preview["chunk_size"]:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST, detail="chunk_overlap must be smaller than chunk_size",
        )
    # Phase 4, Étape 1 (correctif config parent_child) -- same real
    # cross-field discipline, for the two new parent_child-only pairs.
    if merged_preview["parent_chunk_overlap"] >= merged_preview["parent_chunk_size"]:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST, detail="parent_chunk_overlap must be smaller than parent_chunk_size",
        )
    if merged_preview["child_chunk_overlap"] >= merged_preview["child_chunk_size"]:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST, detail="child_chunk_overlap must be smaller than child_chunk_size",
        )

    updated = await update_org_settings(db, org_id, updates)
    await db.commit()
    return OrganizationSettingsResponse(organization_id=org_id, **updated)


# --------------------------------------------------------- BYOK (bring your own key)
#
# Owner-only, same tier as PATCH /settings above and stricter than the
# Admin+ GET -- a real, third-party LLM provider secret is more
# sensitive than any other organization-level setting on this page.


@router.get("/organizations/{org_id}/llm-config", response_model=list[LLMConfigResponse])
async def list_organization_llm_config(
    org_id: uuid.UUID, _caller: OrganizationMember = Depends(require_permission("settings:manage")), db: AsyncSession = Depends(get_db),
):
    return await list_org_llm_configs(db, org_id)


@router.post("/organizations/{org_id}/llm-config", response_model=LLMConfigResponse, status_code=status.HTTP_201_CREATED)
async def set_organization_llm_config(
    org_id: uuid.UUID, payload: LLMConfigSetRequest,
    caller: OrganizationMember = Depends(require_permission("settings:manage")), db: AsyncSession = Depends(get_db),
):
    try:
        config = await set_org_llm_config(db, org_id, payload.provider, payload.api_key, created_by=caller.user_id)
    except UnknownLLMProviderError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc
    await db.commit()
    return config


@router.delete("/organizations/{org_id}/llm-config/{provider}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_organization_llm_config(
    org_id: uuid.UUID, provider: str, _caller: OrganizationMember = Depends(require_permission("settings:manage")), db: AsyncSession = Depends(get_db),
):
    deleted = await delete_org_llm_config(db, org_id, provider)
    if not deleted:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="No BYOK key configured for this provider")
    await db.commit()
