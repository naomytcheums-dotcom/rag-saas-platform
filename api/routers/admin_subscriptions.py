"""Partie 11.4 -- platform-admin subscription/plan management. See
api/services/admin_subscriptions.py's own docstring for this module's
honest scope: real CRUD and real math, zero real payment processor."""

import uuid

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.ext.asyncio import AsyncSession

from api.dependencies import get_db, require_admin
from api.models.user import User
from api.schemas.admin_dashboard import (
    PlanCreateRequest,
    PlanResponse,
    PlanUpdateRequest,
    RevenueStatsResponse,
    SubscriptionCancelRequest,
    SubscriptionExtendRequest,
    SubscriptionResponse,
    SubscriptionUpdateRequest,
)
from api.services.admin_subscriptions import (
    PlanNotFoundError,
    SubscriptionNotFoundError,
    cancel_subscription,
    create_plan,
    delete_plan,
    extend_subscription,
    get_revenue_stats,
    get_subscription,
    list_plans,
    list_subscriptions,
    update_plan,
    update_subscription,
)
from api.utils import MAX_PAGE_SIZE

router = APIRouter(prefix="/admin", tags=["Admin Subscriptions"])


@router.get("/subscriptions", response_model=list[SubscriptionResponse])
async def list_subscriptions_endpoint(limit: int = Query(default=20, ge=1, le=MAX_PAGE_SIZE), offset: int = Query(default=0, ge=0), _admin: User = Depends(require_admin), db: AsyncSession = Depends(get_db)):
    return [SubscriptionResponse.model_validate(s) for s in await list_subscriptions(db, limit, offset)]


@router.get("/subscriptions/stats", response_model=RevenueStatsResponse)
async def get_subscription_stats_endpoint(_admin: User = Depends(require_admin), db: AsyncSession = Depends(get_db)):
    return RevenueStatsResponse(**await get_revenue_stats(db))


@router.get("/subscriptions/{sub_id}", response_model=SubscriptionResponse)
async def get_subscription_endpoint(sub_id: uuid.UUID, _admin: User = Depends(require_admin), db: AsyncSession = Depends(get_db)):
    try:
        sub = await get_subscription(db, sub_id)
    except SubscriptionNotFoundError:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Not found")
    return SubscriptionResponse.model_validate(sub)


@router.patch("/subscriptions/{sub_id}", response_model=SubscriptionResponse)
async def update_subscription_endpoint(sub_id: uuid.UUID, payload: SubscriptionUpdateRequest, _admin: User = Depends(require_admin), db: AsyncSession = Depends(get_db)):
    try:
        sub = await update_subscription(db, sub_id, plan_id=payload.plan_id, status_value=payload.status)
    except SubscriptionNotFoundError:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Not found")
    await db.commit()
    return SubscriptionResponse.model_validate(sub)


@router.post("/subscriptions/{sub_id}/cancel", response_model=SubscriptionResponse)
async def cancel_subscription_endpoint(sub_id: uuid.UUID, payload: SubscriptionCancelRequest, _admin: User = Depends(require_admin), db: AsyncSession = Depends(get_db)):
    """Real, deliberate: POST, not DELETE -- a DELETE carrying a JSON
    body (the cancellation reason) is non-standard and unsupported by
    several real HTTP clients (httpx's own `.delete()` convenience
    method refuses a `json=` kwarg outright, caught by this router's
    own tests) -- the literal spec's `DELETE /admin/subscriptions/{id}`
    is kept working too, see below, but without a body."""
    try:
        sub = await cancel_subscription(db, sub_id, reason=payload.reason)
    except SubscriptionNotFoundError:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Not found")
    await db.commit()
    return SubscriptionResponse.model_validate(sub)


@router.delete("/subscriptions/{sub_id}", response_model=SubscriptionResponse)
async def delete_subscription_endpoint(sub_id: uuid.UUID, _admin: User = Depends(require_admin), db: AsyncSession = Depends(get_db)):
    """The literal spec's own `DELETE /admin/subscriptions/{id}` --
    same real cancel, no reason (real HTTP DELETE carries no body)."""
    try:
        sub = await cancel_subscription(db, sub_id, reason=None)
    except SubscriptionNotFoundError:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Not found")
    await db.commit()
    return SubscriptionResponse.model_validate(sub)


@router.post("/subscriptions/{sub_id}/refund")
async def refund_subscription_endpoint(sub_id: uuid.UUID, _admin: User = Depends(require_admin), db: AsyncSession = Depends(get_db)):
    """Real, honest response: with no real payment processor wired
    (Partie 12, 0/23), there is no real charge to reverse -- refuses
    rather than pretending to move real money."""
    try:
        await get_subscription(db, sub_id)
    except SubscriptionNotFoundError:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Not found")
    raise HTTPException(status_code=status.HTTP_501_NOT_IMPLEMENTED, detail="No real payment processor is configured in this environment -- there is no real charge to refund.")


@router.post("/subscriptions/{sub_id}/extend", response_model=SubscriptionResponse)
async def extend_subscription_endpoint(sub_id: uuid.UUID, payload: SubscriptionExtendRequest, _admin: User = Depends(require_admin), db: AsyncSession = Depends(get_db)):
    try:
        sub = await extend_subscription(db, sub_id, days=payload.days)
    except SubscriptionNotFoundError:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Not found")
    await db.commit()
    return SubscriptionResponse.model_validate(sub)


@router.get("/plans", response_model=list[PlanResponse])
async def list_plans_endpoint(_admin: User = Depends(require_admin), db: AsyncSession = Depends(get_db)):
    plans = await list_plans(db)
    await db.commit()
    return [PlanResponse.model_validate(p) for p in plans]


@router.post("/plans", response_model=PlanResponse, status_code=status.HTTP_201_CREATED)
async def create_plan_endpoint(payload: PlanCreateRequest, _admin: User = Depends(require_admin), db: AsyncSession = Depends(get_db)):
    plan = await create_plan(db, **payload.model_dump())
    await db.commit()
    return PlanResponse.model_validate(plan)


@router.patch("/plans/{plan_id}", response_model=PlanResponse)
async def update_plan_endpoint(plan_id: uuid.UUID, payload: PlanUpdateRequest, _admin: User = Depends(require_admin), db: AsyncSession = Depends(get_db)):
    try:
        plan = await update_plan(db, plan_id, **payload.model_dump())
    except PlanNotFoundError:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Not found")
    await db.commit()
    return PlanResponse.model_validate(plan)


@router.delete("/plans/{plan_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_plan_endpoint(plan_id: uuid.UUID, _admin: User = Depends(require_admin), db: AsyncSession = Depends(get_db)):
    try:
        await delete_plan(db, plan_id)
    except PlanNotFoundError:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Not found")
    await db.commit()


# -- Phase 5, Étape 3 correctif: billing_stripe_sync.py was real,
# complete code with ZERO callers anywhere in this codebase (confirmed
# by audit, Phase 5 Étape 2's own ROADMAP entry) -- the right fix is to
# wire it, not delete working code nor leave it silently unreachable.
# These two endpoints are the only way to actually invoke it.

@router.post("/plans/sync/stripe-products", status_code=status.HTTP_200_OK)
async def sync_stripe_products_endpoint(_admin: User = Depends(require_admin), db: AsyncSession = Depends(get_db)):
    from api.services.billing_stripe import StripeNotConfiguredError
    from api.services.billing_stripe_sync import sync_stripe_products

    try:
        synced = await sync_stripe_products(db)
    except StripeNotConfiguredError as exc:
        raise HTTPException(status_code=status.HTTP_501_NOT_IMPLEMENTED, detail=str(exc))
    await db.commit()
    return {"synced": synced}


@router.post("/plans/sync/stripe-prices", status_code=status.HTTP_200_OK)
async def sync_stripe_prices_endpoint(_admin: User = Depends(require_admin), db: AsyncSession = Depends(get_db)):
    from api.services.billing_stripe import StripeNotConfiguredError
    from api.services.billing_stripe_sync import sync_stripe_prices

    try:
        synced = await sync_stripe_prices(db)
    except StripeNotConfiguredError as exc:
        raise HTTPException(status_code=status.HTTP_501_NOT_IMPLEMENTED, detail=str(exc))
    await db.commit()
    return {"synced": synced}
