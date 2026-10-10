"""Spec 12.1.4 -- promo codes. Superadmin creates and lists them (`/admin/coupons`); an organization owner/admin redeems one
(`POST /organizations/{org_id}/billing/coupons/redeem`). Redeeming a `bonus_credits` code adds the credits at once, in one transaction with the
redemption row, and a code can be used only once per organization and never above `max_redemptions`."""

import datetime as dt
import uuid
from typing import Literal

from fastapi import APIRouter, Depends, HTTPException, Request, status
from pydantic import BaseModel, ConfigDict, Field, model_validator
from sqlalchemy import select, update
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from api.dependencies import get_db, require_superadmin
from api.models.audit_log import AuditAction
from api.models.coupon import Coupon, CouponRedemption
from api.models.organization import OrganizationMember
from api.models.user import User
from api.security.audit_log import log_audit_action
from api.security.organizations import require_org_admin
from api.services.billing_credits import grant_credits
from api.utils import client_ip

router = APIRouter(tags=["coupons"])

_INVALID = HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="This promo code is invalid, expired or already used")


class CouponCreateRequest(BaseModel):
    code: str = Field(min_length=4, max_length=64, pattern=r"^[A-Za-z0-9_-]+$")
    kind: Literal["bonus_credits", "percent_off"]
    bonus_credits: int | None = Field(default=None, ge=1, le=10_000_000)
    percent_off: int | None = Field(default=None, ge=1, le=100)
    max_redemptions: int | None = Field(default=None, ge=1)
    expires_at: dt.datetime | None = None

    @model_validator(mode="after")
    def _check_kind(self):
        if self.kind == "bonus_credits" and (self.bonus_credits is None or self.percent_off is not None):
            raise ValueError("a bonus_credits coupon needs bonus_credits (and no percent_off)")
        if self.kind == "percent_off" and (self.percent_off is None or self.bonus_credits is not None):
            raise ValueError("a percent_off coupon needs percent_off (and no bonus_credits)")
        return self


class CouponUpdateRequest(BaseModel):
    active: bool | None = None
    expires_at: dt.datetime | None = None
    max_redemptions: int | None = Field(default=None, ge=1)


class CouponResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    code: str
    kind: str
    bonus_credits: int | None
    percent_off: int | None
    max_redemptions: int | None
    redeemed_count: int
    expires_at: dt.datetime | None
    active: bool
    created_at: dt.datetime


class RedeemRequest(BaseModel):
    code: str = Field(min_length=1, max_length=64)


class RedeemResponse(BaseModel):
    kind: str
    bonus_credits: int | None = None
    percent_off: int | None = None
    message: str


def _aware(value: dt.datetime) -> dt.datetime:
    return value if value.tzinfo else value.replace(tzinfo=dt.timezone.utc)


@router.post("/admin/coupons", response_model=CouponResponse, status_code=status.HTTP_201_CREATED)
async def create_coupon(payload: CouponCreateRequest, admin: User = Depends(require_superadmin), db: AsyncSession = Depends(get_db)):
    code = payload.code.upper()
    if await db.scalar(select(Coupon.id).where(Coupon.code == code)) is not None:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="This code already exists")
    coupon = Coupon(code=code, kind=payload.kind, bonus_credits=payload.bonus_credits, percent_off=payload.percent_off,
                    max_redemptions=payload.max_redemptions, expires_at=payload.expires_at, created_by=admin.id)
    db.add(coupon)
    await db.commit()
    await db.refresh(coupon)
    return coupon


@router.get("/admin/coupons", response_model=list[CouponResponse])
async def list_coupons(_admin: User = Depends(require_superadmin), db: AsyncSession = Depends(get_db)):
    return list((await db.scalars(select(Coupon).order_by(Coupon.created_at.desc()))).all())


@router.patch("/admin/coupons/{coupon_id}", response_model=CouponResponse)
async def update_coupon(coupon_id: uuid.UUID, payload: CouponUpdateRequest, _admin: User = Depends(require_superadmin), db: AsyncSession = Depends(get_db)):
    coupon = await db.get(Coupon, coupon_id)
    if coupon is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Not found")
    for field, value in payload.model_dump(exclude_unset=True).items():
        setattr(coupon, field, value)
    await db.commit()
    await db.refresh(coupon)
    return coupon


@router.post("/organizations/{org_id}/billing/coupons/redeem", response_model=RedeemResponse)
async def redeem_coupon(
    org_id: uuid.UUID, payload: RedeemRequest, request: Request, caller: OrganizationMember = Depends(require_org_admin), db: AsyncSession = Depends(get_db),
):
    coupon = await db.scalar(select(Coupon).where(Coupon.code == payload.code.strip().upper()))
    now = dt.datetime.now(dt.timezone.utc)
    if coupon is None or not coupon.active or (coupon.expires_at is not None and _aware(coupon.expires_at) <= now):
        raise _INVALID
    if await db.scalar(select(CouponRedemption.id).where(CouponRedemption.coupon_id == coupon.id, CouponRedemption.organization_id == org_id)) is not None:
        raise _INVALID
    # Atomic claim of one redemption slot: the UPDATE only matches while the limit is not reached, so two concurrent redemptions cannot both pass.
    claim = update(Coupon).where(Coupon.id == coupon.id)
    if coupon.max_redemptions is not None:
        claim = claim.where(Coupon.redeemed_count < coupon.max_redemptions)
    claimed = await db.execute(claim.values(redeemed_count=Coupon.redeemed_count + 1))
    if claimed.rowcount != 1:
        raise _INVALID
    db.add(CouponRedemption(coupon_id=coupon.id, organization_id=org_id, user_id=caller.user_id))
    try:
        await db.flush()
    except IntegrityError as exc:  # same organization redeeming twice at the same moment
        await db.rollback()
        raise _INVALID from exc
    if coupon.kind == "bonus_credits":
        await grant_credits(db, org_id, int(coupon.bonus_credits or 0), source=f"coupon:{coupon.code}", user_id=caller.user_id)
    await log_audit_action(
        db, user_id=caller.user_id, action=AuditAction.COUPON_REDEEMED, ip=client_ip(request), user_agent=request.headers.get("user-agent"), success=True,
        organization_id=org_id, resource_type="coupon", resource_id=str(coupon.id), metadata={"kind": coupon.kind},
    )
    await db.commit()
    if coupon.kind == "bonus_credits":
        return RedeemResponse(kind=coupon.kind, bonus_credits=coupon.bonus_credits, message=f"{coupon.bonus_credits} credits were added to your organization")
    return RedeemResponse(kind=coupon.kind, percent_off=coupon.percent_off, message="Your discount code was recorded. It is not applied automatically at checkout yet: contact support to have it applied")
