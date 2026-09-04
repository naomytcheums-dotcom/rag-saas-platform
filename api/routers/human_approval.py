"""
Partie 5.1.10 -- reviewing and deciding real human-approval requests.

**A real, documented deviation from this étape's own literal paths**
(`/approvals/...`, no organization, no stated role tier): mounted under
`/organizations/{org_id}/approvals/...`, matching this codebase's
established multi-tenant convention -- see api/models/human_approval.py's
own docstring for why the row itself carries a real `organization_id`.
Approving/rejecting a SENSITIVE action is itself judged a sensitive
action, gated `require_org_admin` (the same "approving is not a Member-
tier action" reasoning `api/routers/quotas.py` already applies to
raising a quota limit); reading a specific approval's status stays
`require_org_member` -- any real member should be able to check on a
request they know the id of.
"""

import uuid

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

from api.dependencies import get_db
from api.models.human_approval import HumanApproval
from api.models.organization import OrganizationMember
from api.schemas.human_approval import HumanApprovalDecisionRequest, HumanApprovalResponse
from api.security.human_approval import (
    approve_human_request, get_approval_status, list_pending_approvals_for_organization, reject_human_request,
)
from api.security.organizations import require_org_admin, require_org_member

router = APIRouter(tags=["human-approval"])


@router.get("/organizations/{org_id}/approvals/pending", response_model=list[HumanApprovalResponse])
async def get_organization_pending_approvals(
    org_id: uuid.UUID, _caller: OrganizationMember = Depends(require_org_admin), db: AsyncSession = Depends(get_db),
):
    return await list_pending_approvals_for_organization(db, org_id)


@router.post("/organizations/{org_id}/approvals/{approval_id}/approve", response_model=HumanApprovalResponse)
async def approve_approval(
    org_id: uuid.UUID, approval_id: uuid.UUID, payload: HumanApprovalDecisionRequest,
    caller: OrganizationMember = Depends(require_org_admin), db: AsyncSession = Depends(get_db),
):
    approval = await approve_human_request(db, approval_id, caller.user_id, payload.comment)
    if approval is None or approval.organization_id != org_id:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Not found")
    await db.commit()
    return approval


@router.post("/organizations/{org_id}/approvals/{approval_id}/reject", response_model=HumanApprovalResponse)
async def reject_approval(
    org_id: uuid.UUID, approval_id: uuid.UUID, payload: HumanApprovalDecisionRequest,
    caller: OrganizationMember = Depends(require_org_admin), db: AsyncSession = Depends(get_db),
):
    approval = await reject_human_request(db, approval_id, caller.user_id, payload.comment)
    if approval is None or approval.organization_id != org_id:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Not found")
    await db.commit()
    return approval


@router.get("/organizations/{org_id}/approvals/{approval_id}", response_model=HumanApprovalResponse)
async def get_approval(
    org_id: uuid.UUID, approval_id: uuid.UUID,
    _caller: OrganizationMember = Depends(require_org_member), db: AsyncSession = Depends(get_db),
):
    status_value = await get_approval_status(db, approval_id)
    if status_value is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Not found")
    approval = await db.get(HumanApproval, approval_id)
    if approval.organization_id != org_id:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Not found")
    return approval
