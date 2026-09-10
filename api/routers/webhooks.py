"""Partie 9.2.7 -- Webhooks. Real, JWT-authenticated, Admin+, same
`require_key_org_admin`-style pattern for the `/webhooks/{webhook_id}`
routes that have no `org_id` in their own real path."""

import uuid

from fastapi import APIRouter, Depends, HTTPException, Request, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from api.dependencies import get_current_user, get_db
from api.models.audit_log import AuditAction
from api.models.organization import OrganizationMember, OrganizationRole
from api.models.user import User
from api.models.webhook import Webhook
from api.schemas.webhooks import WebhookCreateRequest, WebhookDeliveryResponse, WebhookResponse, WebhookUpdateRequest
from api.security.audit_log import log_audit_action
from api.security.organizations import require_org_admin
from api.services.webhooks import WebhookError, create_webhook, delete_webhook, list_webhook_deliveries, list_webhooks, send_test_delivery, update_webhook
from api.utils import client_ip

router = APIRouter(tags=["Webhooks"])

_NOT_FOUND = HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Not found")


async def _require_webhook_org_admin(webhook_id: uuid.UUID, current_user: User = Depends(get_current_user), db: AsyncSession = Depends(get_db)) -> Webhook:
    webhook = await db.get(Webhook, webhook_id)
    if webhook is None:
        raise _NOT_FOUND
    membership = await db.scalar(
        select(OrganizationMember).where(OrganizationMember.organization_id == webhook.organization_id, OrganizationMember.user_id == current_user.id)
    )
    if membership is None:
        raise _NOT_FOUND
    if membership.role not in (OrganizationRole.owner, OrganizationRole.admin):
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Organization admin access required")
    return webhook


@router.post("/organizations/{org_id}/webhooks", response_model=WebhookResponse)
async def create_webhook_endpoint(
    org_id: uuid.UUID, payload: WebhookCreateRequest, request: Request, caller: OrganizationMember = Depends(require_org_admin), db: AsyncSession = Depends(get_db),
):
    try:
        webhook = await create_webhook(db, org_id, payload.name, payload.url, payload.events, headers=payload.headers, secret=payload.secret, created_by=caller.user_id)
    except WebhookError as exc:
        await db.rollback()
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc
    await log_audit_action(
        db, user_id=caller.user_id, action=AuditAction.WEBHOOK_CREATED, ip=client_ip(request), user_agent=request.headers.get("user-agent"),
        success=True, organization_id=org_id, resource_type="webhook", resource_id=str(webhook.id), metadata={"name": webhook.name, "url": webhook.url},
    )
    await db.commit()
    return webhook


@router.get("/organizations/{org_id}/webhooks", response_model=list[WebhookResponse])
async def list_webhooks_endpoint(org_id: uuid.UUID, _caller: OrganizationMember = Depends(require_org_admin), db: AsyncSession = Depends(get_db)):
    return await list_webhooks(db, org_id)


@router.get("/webhooks/{webhook_id}", response_model=WebhookResponse)
async def get_webhook_endpoint(webhook: Webhook = Depends(_require_webhook_org_admin)):
    return webhook


@router.patch("/webhooks/{webhook_id}", response_model=WebhookResponse)
async def update_webhook_endpoint(payload: WebhookUpdateRequest, webhook: Webhook = Depends(_require_webhook_org_admin), db: AsyncSession = Depends(get_db)):
    try:
        updated = await update_webhook(db, webhook.id, **payload.model_dump(exclude_unset=True))
    except WebhookError as exc:
        await db.rollback()
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc
    await db.commit()
    await db.refresh(updated)
    return updated


@router.delete("/webhooks/{webhook_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_webhook_endpoint(request: Request, webhook: Webhook = Depends(_require_webhook_org_admin), current_user: User = Depends(get_current_user), db: AsyncSession = Depends(get_db)):
    await delete_webhook(db, webhook.id)
    await log_audit_action(
        db, user_id=current_user.id, action=AuditAction.WEBHOOK_DELETED, ip=client_ip(request), user_agent=request.headers.get("user-agent"),
        success=True, organization_id=webhook.organization_id, resource_type="webhook", resource_id=str(webhook.id),
    )
    await db.commit()


@router.get("/webhooks/{webhook_id}/deliveries", response_model=list[WebhookDeliveryResponse])
async def list_webhook_deliveries_endpoint(webhook: Webhook = Depends(_require_webhook_org_admin), db: AsyncSession = Depends(get_db)):
    return await list_webhook_deliveries(db, webhook.id)


@router.post("/webhooks/{webhook_id}/test", response_model=WebhookDeliveryResponse)
async def test_webhook_endpoint(webhook: Webhook = Depends(_require_webhook_org_admin), db: AsyncSession = Depends(get_db)):
    delivery = await send_test_delivery(db, webhook)
    await db.commit()
    await db.refresh(delivery)
    return delivery
