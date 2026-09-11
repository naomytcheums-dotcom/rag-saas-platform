"""
Partie 16 (bis) -- self-hosted licensing (superadmin-issued, publicly
validated), hybrid support tickets/SLA (org-scoped), white-label
reseller/sub-client (superadmin-scoped, since a reseller relationship
spans two organizations -- not one org's own data).
"""

import uuid

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

from api.dependencies import get_db, require_superadmin
from api.models.organization import OrganizationMember
from api.models.user import User
from api.schemas.sales import (
    ActivateLicenseRequest, AddSubClientRequest, CreateResellerRequest, CreateTicketRequest, GenerateLicenseRequest,
    LicenseResponse, ResellerResponse, RespondTicketRequest, SubClientResponse, TicketMessageResponse,
    TicketResponseModel, ValidateLicenseRequest,
)
from api.security.organizations import require_org_admin, require_org_member
from api.services import sales

router = APIRouter(tags=["Sales"])
org_router = APIRouter(prefix="/organizations/{org_id}", tags=["Sales"])


# -- Self-hosted licensing ----------------------------------------------------

@router.post("/license/generate", response_model=LicenseResponse, status_code=status.HTTP_201_CREATED)
async def generate_license_endpoint(body: GenerateLicenseRequest, _admin: User = Depends(require_superadmin), db: AsyncSession = Depends(get_db)):
    license_row = await sales.generate_license(db, plan_key=body.plan_key, max_activations=body.max_activations, expires_in_days=body.expires_in_days)
    await db.commit()
    return license_row


@router.post("/license/validate")
async def validate_license_endpoint(body: ValidateLicenseRequest, db: AsyncSession = Depends(get_db)):
    """Public -- a self-hosted deployment with no logged-in user yet
    (e.g. checking on startup) still needs to validate its own key."""
    result = await sales.validate_license(db, body.key)
    await db.commit()
    return result


@org_router.post("/license/activate", response_model=LicenseResponse)
async def activate_license_endpoint(org_id: uuid.UUID, body: ActivateLicenseRequest, _caller: OrganizationMember = Depends(require_org_admin), db: AsyncSession = Depends(get_db)):
    try:
        license_row = await sales.activate_license(db, body.key, org_id)
    except sales.LicenseNotFoundError:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Unknown license key")
    except sales.SalesError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc))
    await db.commit()
    return license_row


@org_router.get("/license/status", response_model=LicenseResponse | None)
async def license_status_endpoint(org_id: uuid.UUID, _caller: OrganizationMember = Depends(require_org_member), db: AsyncSession = Depends(get_db)):
    return await sales.get_license_status(db, org_id)


# -- Hybrid: support tickets --------------------------------------------------

@org_router.post("/support/tickets", response_model=TicketResponseModel, status_code=status.HTTP_201_CREATED)
async def create_ticket_endpoint(org_id: uuid.UUID, body: CreateTicketRequest, caller: OrganizationMember = Depends(require_org_member), db: AsyncSession = Depends(get_db)):
    ticket = await sales.create_support_ticket(db, org_id, subject=body.subject, description=body.description, priority=body.priority, user_id=caller.user_id)
    await db.commit()
    return ticket


@org_router.get("/support/tickets", response_model=list[TicketResponseModel])
async def list_tickets_endpoint(org_id: uuid.UUID, _caller: OrganizationMember = Depends(require_org_member), db: AsyncSession = Depends(get_db)):
    return await sales.list_support_tickets(db, org_id)


@org_router.get("/support/tickets/{ticket_id}/sla")
async def ticket_sla_endpoint(org_id: uuid.UUID, ticket_id: uuid.UUID, _caller: OrganizationMember = Depends(require_org_member), db: AsyncSession = Depends(get_db)):
    try:
        ticket = await sales.get_support_ticket(db, org_id, ticket_id)
    except sales.TicketNotFoundError:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Ticket not found")
    return sales.get_sla_status(ticket)


@org_router.post("/support/tickets/{ticket_id}/respond", response_model=TicketMessageResponse, status_code=status.HTTP_201_CREATED)
async def respond_ticket_endpoint(org_id: uuid.UUID, ticket_id: uuid.UUID, body: RespondTicketRequest, caller: OrganizationMember = Depends(require_org_member), db: AsyncSession = Depends(get_db)):
    try:
        response = await sales.respond_to_ticket(db, org_id, ticket_id, body=body.body, is_staff=False, user_id=caller.user_id)
    except sales.TicketNotFoundError:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Ticket not found")
    await db.commit()
    return response


# -- White-label: reseller / sub-clients (platform-level) --------------------

@router.post("/reseller/create", response_model=ResellerResponse, status_code=status.HTTP_201_CREATED)
async def create_reseller_endpoint(body: CreateResellerRequest, _admin: User = Depends(require_superadmin), db: AsyncSession = Depends(get_db)):
    reseller = await sales.create_reseller(db, body.organization_id, commission_percent=body.commission_percent)
    await db.commit()
    return reseller


@router.post("/reseller/{reseller_id}/clients", response_model=SubClientResponse, status_code=status.HTTP_201_CREATED)
async def add_sub_client_endpoint(reseller_id: uuid.UUID, body: AddSubClientRequest, _admin: User = Depends(require_superadmin), db: AsyncSession = Depends(get_db)):
    try:
        sub_client = await sales.add_sub_client(db, reseller_id, body.organization_id)
    except sales.ResellerNotFoundError:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Reseller not found")
    await db.commit()
    return sub_client


@router.get("/reseller/{reseller_id}/clients", response_model=list[SubClientResponse])
async def list_reseller_clients_endpoint(reseller_id: uuid.UUID, _admin: User = Depends(require_superadmin), db: AsyncSession = Depends(get_db)):
    return await sales.list_sub_clients(db, reseller_id)


@router.get("/reseller/{reseller_id}/commission")
async def reseller_commission_endpoint(reseller_id: uuid.UUID, _admin: User = Depends(require_superadmin), db: AsyncSession = Depends(get_db)):
    try:
        return await sales.calculate_reseller_commission(db, reseller_id)
    except sales.ResellerNotFoundError:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Reseller not found")
