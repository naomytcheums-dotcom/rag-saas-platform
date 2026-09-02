"""
Partie 1.4.1 -- registering, listing, deleting, and verifying an
organization's custom domains.

POST/GET/DELETE are Owner-only, same boundary as quotas'/settings'/
branding's PATCH: pointing a domain at the organization (and the DNS
instructions that implies) is an organization-level decision.

GET .../domains/verify/{token} is deliberately PUBLIC, same posture as
Partie 1.3.10's GET .../branding and api/routers/password.py's
reset_password: the token itself (32 random bytes, see
api/security/custom_domains.py's add_custom_domain) is the proof of
authorization, not a session -- an Owner clicks this link (or a script
polls it) after configuring DNS, before necessarily being logged back in.
"""

import datetime as dt
import uuid

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import delete, select
from sqlalchemy.ext.asyncio import AsyncSession

from api.config import settings
from api.dependencies import get_db
from api.models.custom_domain import CustomDomain, CustomDomainStatus
from api.models.organization import OrganizationMember
from api.schemas.custom_domains import (
    CustomDomainCreateRequest,
    CustomDomainListResponse,
    CustomDomainResponse,
    CustomDomainStatusResponse,
    DnsRecordEntry,
)
from api.security.custom_domains import (
    activate_domain,
    add_custom_domain,
    dns_records_for,
    setup_steps,
    trigger_manual_verification,
    verify_domain,
)
from api.security.organizations import require_org_owner

router = APIRouter(tags=["custom-domains"])


def _to_response(row: CustomDomain) -> CustomDomainResponse:
    return CustomDomainResponse(
        id=row.id, organization_id=row.organization_id, domain=row.domain, status=row.status,
        verification_token=row.verification_token,
        verification_attempts=row.verification_attempts, last_verification_attempt_at=row.last_verification_attempt_at,
        dns_records=[DnsRecordEntry(**record) for record in dns_records_for(row.domain, row.verification_token)],
        setup_steps=setup_steps(),
        created_at=row.created_at, updated_at=row.updated_at,
    )


async def _get_owned_domain(db: AsyncSession, org_id: uuid.UUID, domain_id: uuid.UUID) -> CustomDomain:
    domain = await db.scalar(select(CustomDomain).where(CustomDomain.id == domain_id, CustomDomain.organization_id == org_id))
    if domain is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Not found")
    return domain


@router.post("/organizations/{org_id}/domains", response_model=CustomDomainResponse, status_code=status.HTTP_201_CREATED)
async def create_custom_domain(
    org_id: uuid.UUID, payload: CustomDomainCreateRequest,
    _caller: OrganizationMember = Depends(require_org_owner), db: AsyncSession = Depends(get_db),
):
    try:
        domain = await add_custom_domain(db, org_id, payload.domain)
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc))

    await db.commit()
    await db.refresh(domain)
    return _to_response(domain)


@router.get("/organizations/{org_id}/domains", response_model=CustomDomainListResponse)
async def list_custom_domains(
    org_id: uuid.UUID, _caller: OrganizationMember = Depends(require_org_owner), db: AsyncSession = Depends(get_db),
):
    rows = (await db.scalars(
        select(CustomDomain).where(CustomDomain.organization_id == org_id).order_by(CustomDomain.created_at.asc())
    )).all()
    return CustomDomainListResponse(items=[_to_response(row) for row in rows])


@router.delete("/organizations/{org_id}/domains/{domain_id}")
async def delete_custom_domain(
    org_id: uuid.UUID, domain_id: uuid.UUID,
    _caller: OrganizationMember = Depends(require_org_owner), db: AsyncSession = Depends(get_db),
):
    domain = await db.scalar(select(CustomDomain).where(CustomDomain.id == domain_id, CustomDomain.organization_id == org_id))
    if domain is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Not found")

    await db.execute(delete(CustomDomain).where(CustomDomain.id == domain.id))
    await db.commit()
    return {"message": "Domain deleted"}


@router.get("/organizations/{org_id}/domains/verify/{token}", response_model=CustomDomainResponse)
async def verify_custom_domain(org_id: uuid.UUID, token: str, db: AsyncSession = Depends(get_db)):
    """
    Public. Looks up the pending row by (org_id, token) FIRST -- a
    non-matching combination 404s before any DNS lookup happens, so
    this can't be abused as an arbitrary DNS-lookup proxy against a
    domain of the caller's choosing. On a successful DNS match,
    immediately activates the domain too (see
    api/security/custom_domains.py's activate_domain docstring for why
    nothing else currently gates that second step). On a failed match,
    returns 200 with status="failed" and the same DNS instructions --
    not an error, since "not propagated yet" is the expected common
    case, and the Owner can simply request this same link again once
    their DNS has updated.
    """
    domain = await db.scalar(
        select(CustomDomain).where(CustomDomain.organization_id == org_id, CustomDomain.verification_token == token)
    )
    if domain is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Not found")

    updated = await verify_domain(db, domain.domain, token)
    if updated.status == CustomDomainStatus.verified.value:
        updated = await activate_domain(db, updated.domain)

    await db.commit()
    # updated_at has onupdate=func.now() -- see api/routers/organizations.py's
    # update_organization for why an explicit refresh is required here
    # (an implicit sync-style reload would raise MissingGreenlet under
    # this async session).
    await db.refresh(updated)
    return _to_response(updated)


@router.post("/organizations/{org_id}/domains/{domain_id}/verify", response_model=CustomDomainResponse)
async def verify_custom_domain_manual(
    org_id: uuid.UUID, domain_id: uuid.UUID,
    _caller: OrganizationMember = Depends(require_org_owner), db: AsyncSession = Depends(get_db),
):
    """
    Partie 1.4.4 -- an Owner-authenticated "verify now" button, distinct
    from the public token link above: same immediate, single-shot DNS
    check (api/security/custom_domains.py's trigger_manual_verification),
    but deliberately does NOT count against
    DOMAIN_VERIFICATION_MAX_ATTEMPTS/_TIMEOUT_MINUTES -- those bound the
    automatic periodic sweep, not a human clicking a button.
    """
    domain = await _get_owned_domain(db, org_id, domain_id)
    updated = await trigger_manual_verification(db, domain)
    await db.commit()
    await db.refresh(updated)
    return _to_response(updated)


@router.get("/organizations/{org_id}/domains/{domain_id}/status", response_model=CustomDomainStatusResponse)
async def get_custom_domain_status(
    org_id: uuid.UUID, domain_id: uuid.UUID,
    _caller: OrganizationMember = Depends(require_org_owner), db: AsyncSession = Depends(get_db),
):
    """
    Partie 1.4.4 -- a focused progress view for a dashboard polling "is
    it done yet": attempt count, last attempt time, and a computed
    timeout_at (created_at + DOMAIN_VERIFICATION_TIMEOUT_MINUTES),
    worked out fresh here rather than stored, same reasoning as
    CustomDomainResponse's dns_records.
    """
    domain = await _get_owned_domain(db, org_id, domain_id)
    return CustomDomainStatusResponse(
        id=domain.id, domain=domain.domain, status=domain.status,
        verification_attempts=domain.verification_attempts,
        max_attempts=settings.DOMAIN_VERIFICATION_MAX_ATTEMPTS,
        last_verification_attempt_at=domain.last_verification_attempt_at,
        created_at=domain.created_at,
        timeout_at=domain.created_at + dt.timedelta(minutes=settings.DOMAIN_VERIFICATION_TIMEOUT_MINUTES),
    )
