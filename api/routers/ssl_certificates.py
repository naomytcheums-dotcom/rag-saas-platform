"""
Partie 1.4.3 -- generating, checking, renewing, and revoking a custom
domain's SSL certificate. All four endpoints are Owner-only, same
boundary as every other custom-domain/branding/settings mutation in
this codebase -- unlike Partie 1.4.1's domain verification, there is no
public endpoint here: an SSL certificate's own PEM is not sensitive,
but generating/renewing/revoking one triggers a real, rate-limited
Let's Encrypt request, which is an organization-level decision, not
something to expose without authentication.

See api/security/ssl_certificates.py's module docstring for the real,
two-phase ACME flow these endpoints drive -- generate/renew never
finish issuance in one call unless a certificate was already mid-flight
and Let's Encrypt has now validated it; the normal path is: call
generate, publish the returned DNS-01 TXT record, call generate again.
"""

import uuid

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from api.dependencies import get_db
from api.models.custom_domain import CustomDomain
from api.models.organization import OrganizationMember
from api.models.ssl_certificate import SSLCertificate, SSLCertificateStatus
from api.schemas.ssl_certificates import SSLCertificateResponse, SSLDns01Challenge
from api.security.permissions import require_permission
from api.security.organizations import require_org_owner
from api.security.ssl_certificates import (
    dns01_challenge_instructions,
    generate_ssl_certificate,
    get_certificate,
    renew_ssl_certificate,
    revoke_certificate,
)

router = APIRouter(tags=["ssl-certificates"])


def _to_response(row: SSLCertificate) -> SSLCertificateResponse:
    challenge = None
    if row.status == SSLCertificateStatus.pending_dns01.value:
        challenge = SSLDns01Challenge(
            record_name=row.dns01_record_name, record_value=row.dns01_record_value,
            instructions=dns01_challenge_instructions(row.dns01_record_name, row.dns01_record_value),
        )
    return SSLCertificateResponse(
        domain=row.domain, status=row.status, cert_pem=row.cert_pem, chain_pem=row.chain_pem,
        expires_at=row.expires_at, dns01_challenge=challenge, created_at=row.created_at, updated_at=row.updated_at,
    )


async def _get_owned_domain(db: AsyncSession, org_id: uuid.UUID, domain_id: uuid.UUID) -> CustomDomain:
    domain = await db.scalar(select(CustomDomain).where(CustomDomain.id == domain_id, CustomDomain.organization_id == org_id))
    if domain is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Not found")
    return domain


@router.post("/organizations/{org_id}/domains/{domain_id}/ssl/generate", response_model=SSLCertificateResponse)
async def generate_certificate_route(
    org_id: uuid.UUID, domain_id: uuid.UUID,
    _caller: OrganizationMember = Depends(require_permission("settings:manage")), db: AsyncSession = Depends(get_db),
):
    domain = await _get_owned_domain(db, org_id, domain_id)
    try:
        certificate = await generate_ssl_certificate(db, domain.domain)
    except (ValueError, EnvironmentError) as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc))
    except RuntimeError as exc:
        raise HTTPException(status_code=status.HTTP_502_BAD_GATEWAY, detail=str(exc))

    await db.commit()
    await db.refresh(certificate)
    return _to_response(certificate)


@router.get("/organizations/{org_id}/domains/{domain_id}/ssl", response_model=SSLCertificateResponse)
async def get_certificate_route(
    org_id: uuid.UUID, domain_id: uuid.UUID,
    _caller: OrganizationMember = Depends(require_permission("settings:manage")), db: AsyncSession = Depends(get_db),
):
    domain = await _get_owned_domain(db, org_id, domain_id)
    certificate = await get_certificate(db, domain.domain)
    if certificate is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="No certificate has been requested for this domain")
    return _to_response(certificate)


@router.post("/organizations/{org_id}/domains/{domain_id}/ssl/renew", response_model=SSLCertificateResponse)
async def renew_certificate_route(
    org_id: uuid.UUID, domain_id: uuid.UUID,
    _caller: OrganizationMember = Depends(require_permission("settings:manage")), db: AsyncSession = Depends(get_db),
):
    domain = await _get_owned_domain(db, org_id, domain_id)
    try:
        certificate = await renew_ssl_certificate(db, domain.domain)
    except (ValueError, EnvironmentError) as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc))
    except RuntimeError as exc:
        raise HTTPException(status_code=status.HTTP_502_BAD_GATEWAY, detail=str(exc))

    await db.commit()
    await db.refresh(certificate)
    return _to_response(certificate)


@router.delete("/organizations/{org_id}/domains/{domain_id}/ssl")
async def delete_certificate_route(
    org_id: uuid.UUID, domain_id: uuid.UUID,
    _caller: OrganizationMember = Depends(require_permission("settings:manage")), db: AsyncSession = Depends(get_db),
):
    domain = await _get_owned_domain(db, org_id, domain_id)
    try:
        await revoke_certificate(db, domain.domain)
    except EnvironmentError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc))
    except RuntimeError as exc:
        raise HTTPException(status_code=status.HTTP_502_BAD_GATEWAY, detail=str(exc))

    await db.commit()
    return {"message": "Certificate revoked"}
