"""
Etape 1.2.2 -- the first organization-facing endpoints. Every route here
scopes access through api/security/organizations.py's
require_org_member/admin/owner dependencies rather than checking role by
hand, so the same 404-for-non-members / 403-for-insufficient-role
behavior is guaranteed consistent across every current and future
organization-scoped route.
"""

import logging
import uuid

from fastapi import APIRouter, Depends, HTTPException, Request, status
from sqlalchemy import delete, select
from sqlalchemy.ext.asyncio import AsyncSession

from api.dependencies import get_current_user, get_db
from api.models.audit_log import AuditAction
from api.models.organization import Organization, OrganizationMember, OrganizationRole
from api.models.user import User
from api.schemas.organizations import (
    OrganizationCreateRequest,
    OrganizationEntry,
    OrganizationListResponse,
    OrganizationUpdateRequest,
)
from api.security.permissions import require_permission
from api.security.audit_log import log_audit_action
from api.security.organizations import create_organization_with_owner, require_org_member, require_org_owner
from api.utils import client_ip

router = APIRouter(prefix="/organizations", tags=["organizations"])
logger = logging.getLogger(__name__)


def _to_entry(org: Organization, my_role) -> OrganizationEntry:
    return OrganizationEntry(
        id=org.id, name=org.name, slug=org.slug, my_role=my_role, created_at=org.created_at, updated_at=org.updated_at,
    )


@router.post("", response_model=OrganizationEntry, status_code=status.HTTP_201_CREATED)
async def create_organization(
    payload: OrganizationCreateRequest, request: Request,
    current_user: User = Depends(get_current_user), db: AsyncSession = Depends(get_db),
):
    """The creating user becomes Owner immediately -- see
    create_organization_with_owner's own docstring for why organization
    + owner-membership are created together, atomically."""
    organization = await create_organization_with_owner(
        db, name=payload.name, owner_user_id=current_user.id,
        ip=client_ip(request), user_agent=request.headers.get("user-agent"),
    )
    await db.commit()
    return _to_entry(organization, OrganizationRole.owner)


@router.get("", response_model=OrganizationListResponse)
async def list_my_organizations(current_user: User = Depends(get_current_user), db: AsyncSession = Depends(get_db)):
    rows = (await db.execute(
        select(Organization, OrganizationMember.role)
        .join(OrganizationMember, OrganizationMember.organization_id == Organization.id)
        .where(OrganizationMember.user_id == current_user.id)
        .order_by(Organization.created_at.desc())
    )).all()
    return OrganizationListResponse(items=[_to_entry(org, role) for org, role in rows])


@router.get("/{org_id}", response_model=OrganizationEntry)
async def get_organization(
    org_id: uuid.UUID, membership: OrganizationMember = Depends(require_permission("settings:read")), db: AsyncSession = Depends(get_db),
):
    organization = await db.get(Organization, org_id)
    return _to_entry(organization, membership.role)


@router.patch("/{org_id}", response_model=OrganizationEntry)
async def update_organization(
    org_id: uuid.UUID, payload: OrganizationUpdateRequest,
    # Hardening Mission, Phase 2/4 -- a real, confirmed privilege-escalation
    # bug fix: `require_org_owner` (api/security/organizations.py) already
    # exists and its own docstring explicitly says it "gates PATCH/DELETE
    # /organizations/{id}" -- but this route was actually gated on
    # `require_permission("settings:manage")`, which `_effective_permissions_for`
    # (api/security/permissions.py) resolves to "every permission, no check
    # at all" for Admin (not just Owner) -- a real, reproduced 200 where a
    # 403 was expected (`tests/test_organizations.py::test_a_non_owner_member_cannot_delete_the_organization`,
    # discovered while spot-checking an unrelated fix). An Admin can still
    # do everything else "settings:manage" grants; only renaming/deleting
    # the organization itself is Owner-exclusive, exactly as this
    # dependency's own, already-correct docstring says.
    membership: OrganizationMember = Depends(require_org_owner), db: AsyncSession = Depends(get_db),
):
    organization = await db.get(Organization, org_id)
    organization.name = payload.name
    await db.commit()
    # updated_at has server_onupdate=func.now() -- SQLAlchemy marks it
    # expired after a commit that changes a tracked column, regardless
    # of the session's expire_on_commit setting, since it can't know the
    # new server-computed value without asking. An explicit async-safe
    # refresh here avoids an implicit (sync-only) attribute reload that
    # would otherwise raise MissingGreenlet the moment updated_at is
    # serialized into the response below.
    await db.refresh(organization)
    return _to_entry(organization, membership.role)


@router.delete("/{org_id}")
async def delete_organization(
    org_id: uuid.UUID, request: Request,
    # Hardening Mission, Phase 2/4 -- same real privilege-escalation fix
    # as update_organization above.
    membership: OrganizationMember = Depends(require_org_owner), db: AsyncSession = Depends(get_db),
):
    """Owner only. A plain Core DELETE, not session.delete() -- the
    database's own ON DELETE CASCADE (the Alembic migration) removes
    every organization_members row for this org, same "rely on the FK,
    not an ORM cascade walk" pattern as api/tasks/account_purge.py and
    api/routers/enterprise_sso.py's delete_sso_connection."""
    organization = await db.get(Organization, org_id)
    if organization is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Not found")

    await log_audit_action(
        db, user_id=membership.user_id, action=AuditAction.ORGANIZATION_DELETED, ip=client_ip(request),
        user_agent=request.headers.get("user-agent"), success=True,
        metadata={"organization_id": str(org_id), "name": organization.name},
    )
    # Hardening Mission, Phase 6 -- a real, confirmed GDPR/right-to-be-
    # forgotten gap: deleting an organization used to only ever touch
    # this SQL row (and whatever ON DELETE CASCADE reaches) -- any real
    # mem0 memories or GraphRAG entities/relations this organization had
    # (neither is wired to a live feature yet, but the mission's own
    # rule is to complete a gap, never leave it for whenever that
    # wiring happens) would have survived forever on disk, orphaned.
    # Best-effort, same "an external store hiccup must never block a
    # real organization deletion the caller is already entitled to"
    # reasoning as api/tasks/account_purge.py's own delete_avatar call.
    try:
        from api.services.mem0_service import purge_organization_memory

        await purge_organization_memory(org_id)
    except Exception:  # noqa: BLE001
        logger.warning("delete_organization: mem0 purge failed for organization %s, continuing", org_id)
    try:
        from api.services.graph_rag import purge_organization_graph

        await purge_organization_graph(org_id)
    except Exception:  # noqa: BLE001
        logger.warning("delete_organization: GraphRAG purge failed for organization %s, continuing", org_id)

    await db.execute(delete(Organization).where(Organization.id == org_id))
    await db.commit()
    return {"message": "Organization deleted"}
