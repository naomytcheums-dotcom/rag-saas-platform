"""
Partie 16 (bis) -- self-hosted licensing (superadmin-issued, publicly
validated), hybrid support tickets/SLA (org-scoped), white-label
reseller/sub-client (superadmin-scoped, since a reseller relationship
spans two organizations -- not one org's own data).
"""

import uuid

from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.responses import RedirectResponse
from sqlalchemy.ext.asyncio import AsyncSession

from api.config import settings
from api.dependencies import get_current_user, get_db, require_superadmin
from api.models.organization import OrganizationMember
from api.models.user import User
from api.schemas.sales import (
    ActivateLicenseRequest, AddSubClientRequest, CreateResellerRequest, CreateTicketRequest, GenerateLicenseRequest,
    LicenseResponse, PartnerCommissionResponse, RegisterPartnerRequest, RegisterPartnerResponse, ResellerResponse,
    RespondTicketRequest, SubClientResponse, TicketMessageResponse, TicketResponseModel, ValidateLicenseRequest,
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


# -- Partner program (Partie 18): self-service signup + real commission ledger

@router.post("/partners/register", response_model=RegisterPartnerResponse, status_code=status.HTTP_201_CREATED)
async def register_partner_endpoint(body: RegisterPartnerRequest, db: AsyncSession = Depends(get_db)):
    """Public -- the real front door create_reseller (superadmin-only)
    never had: a prospective partner creates their own account, own
    organization, and their own Reseller row, all in this one call."""
    try:
        _user, reseller = await sales.register_partner(
            db, organization_name=body.organization_name, email=body.email, password=body.password, full_name=body.full_name,
        )
    except sales.EmailAlreadyRegisteredError:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Could not register with these details")
    await db.commit()
    return RegisterPartnerResponse(reseller=reseller)


@router.get("/partners/me", response_model=ResellerResponse)
async def get_my_partner_profile_endpoint(user: User = Depends(get_current_user), db: AsyncSession = Depends(get_db)):
    reseller = await sales.get_reseller_for_user(db, user.id)
    if reseller is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="You are not a registered partner")
    return reseller


@router.get("/partners/me/clients", response_model=list[SubClientResponse])
async def list_my_partner_clients_endpoint(user: User = Depends(get_current_user), db: AsyncSession = Depends(get_db)):
    reseller = await sales.get_reseller_for_user(db, user.id)
    if reseller is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="You are not a registered partner")
    return await sales.list_sub_clients(db, reseller.id)


@router.get("/partners/me/commissions", response_model=list[PartnerCommissionResponse])
async def list_my_partner_commissions_endpoint(user: User = Depends(get_current_user), db: AsyncSession = Depends(get_db)):
    reseller = await sales.get_reseller_for_user(db, user.id)
    if reseller is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="You are not a registered partner")
    return await sales.list_partner_commissions(db, reseller.id)


@router.get("/partners/{reseller_id}/commissions", response_model=list[PartnerCommissionResponse])
async def list_partner_commissions_endpoint(reseller_id: uuid.UUID, _admin: User = Depends(require_superadmin), db: AsyncSession = Depends(get_db)):
    try:
        await sales.get_reseller(db, reseller_id)
    except sales.ResellerNotFoundError:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Reseller not found")
    return await sales.list_partner_commissions(db, reseller_id)


@router.get("/r/{code}")
async def referral_redirect_endpoint(code: str, db: AsyncSession = Depends(get_db)):
    """Public -- a partner's shareable referral link. Real, honest
    behavior on an unknown/stale code: a plain 404, not a silent
    redirect to the generic registration page (which would let a
    partner "test" random codes and learn which ones are real).
    Setting the cookie here (rather than trusting a query param at
    registration time) means the referral survives the click ->
    "look around the marketing site first" -> registration gap without
    the frontend having to thread `?ref=` through every intermediate
    page itself."""
    reseller = await sales.get_reseller_by_referral_code(db, code)
    if reseller is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Unknown referral code")
    response = RedirectResponse(url=f"{settings.FRONTEND_URL}/register?ref={code}", status_code=status.HTTP_307_TEMPORARY_REDIRECT)
    response.set_cookie(
        key=sales.PARTNER_REFERRAL_COOKIE_NAME, value=code, max_age=sales.PARTNER_REFERRAL_COOKIE_MAX_AGE_SECONDS,
        httponly=True, secure=settings.COOKIE_SECURE, samesite="lax",
    )
    return response


@router.post("/partners/commissions/{commission_id}/pay", response_model=PartnerCommissionResponse)
async def pay_partner_commission_endpoint(commission_id: uuid.UUID, _admin: User = Depends(require_superadmin), db: AsyncSession = Depends(get_db)):
    try:
        commission = await sales.pay_partner_commission(db, commission_id)
    except sales.PartnerCommissionNotFoundError:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Commission not found")
    except sales.SalesError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc))
    await db.commit()
    return commission
