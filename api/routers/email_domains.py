"""
Partie 1.4.5 -- verifying a custom domain for email sending (DKIM +
Resend). All three endpoints are Owner-only, same boundary as every
other custom-domain mutation/read in this codebase -- registering a
domain with a third-party service (Resend) and exposing its DKIM setup
is an organization-level decision, not something to expose without
authentication.

See api/security/email_domains.py's module docstring for the real,
two-track design these endpoints drive: our own self-generated DKIM
keypair (real, testable, but not what Resend actually uses to sign
mail) alongside Resend's own real Domains API integration (what
actually matters for deliverability).
"""

import uuid

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from api.dependencies import get_db
from api.models.custom_domain import CustomDomain
from api.models.organization import OrganizationMember
from api.schemas.email_domains import EmailDnsRecordEntry, EmailDnsResponse, EmailDomainStatusResponse
from api.security.email_domains import get_email_dns_records, get_email_verification_status, verify_email_domain
from api.security.organizations import require_org_owner

router = APIRouter(tags=["email-domains"])


async def _get_owned_domain(db: AsyncSession, org_id: uuid.UUID, domain_id: uuid.UUID) -> CustomDomain:
    domain = await db.scalar(select(CustomDomain).where(CustomDomain.id == domain_id, CustomDomain.organization_id == org_id))
    if domain is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Not found")
    return domain


@router.post("/organizations/{org_id}/domains/{domain_id}/email/verify", response_model=EmailDomainStatusResponse)
async def verify_email_domain_route(
    org_id: uuid.UUID, domain_id: uuid.UUID,
    _caller: OrganizationMember = Depends(require_org_owner), db: AsyncSession = Depends(get_db),
):
    domain = await _get_owned_domain(db, org_id, domain_id)
    updated = await verify_email_domain(db, domain)
    await db.commit()
    await db.refresh(updated)
    return EmailDomainStatusResponse(id=updated.id, domain=updated.domain, **get_email_verification_status(updated))


@router.get("/organizations/{org_id}/domains/{domain_id}/email/status", response_model=EmailDomainStatusResponse)
async def get_email_domain_status_route(
    org_id: uuid.UUID, domain_id: uuid.UUID,
    _caller: OrganizationMember = Depends(require_org_owner), db: AsyncSession = Depends(get_db),
):
    domain = await _get_owned_domain(db, org_id, domain_id)
    return EmailDomainStatusResponse(id=domain.id, domain=domain.domain, **get_email_verification_status(domain))


@router.get("/organizations/{org_id}/domains/{domain_id}/email/dns", response_model=EmailDnsResponse)
async def get_email_domain_dns_route(
    org_id: uuid.UUID, domain_id: uuid.UUID,
    _caller: OrganizationMember = Depends(require_org_owner), db: AsyncSession = Depends(get_db),
):
    domain = await _get_owned_domain(db, org_id, domain_id)
    data = await get_email_dns_records(db, domain)
    await db.commit()
    return EmailDnsResponse(
        our_records=[EmailDnsRecordEntry(**record) for record in data["our_records"]],
        resend_domain_id=data["resend_domain_id"],
        resend_status=data["resend_status"],
        resend_records=data["resend_records"],
        resend_error=data["resend_error"],
    )
