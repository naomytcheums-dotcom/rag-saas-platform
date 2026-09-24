"""Real, org-scoped CRUD for NotificationTemplate + preview + test
(P2 #6, session SSRF épinglé).

The model (api/models/notification_template.py) is the real,
admin-editable override layer on top of the code-defined TEMPLATES
dict in api/services/notification_templates.py.

Lookup at render time:
1. Organization-specific row (organization_id = the org, is_active=True)
2. Global row (organization_id IS NULL, is_active=True)
3. Code-defined TEMPLATES[type]

This router exposes the CRUD for org-specific rows only. Global rows
are managed out-of-band (seed scripts / admin), never through this
org-scoped API.
"""

import uuid

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from api.dependencies import get_db
from api.models.notification_template import NotificationTemplate
from api.models.organization import OrganizationMember
from api.schemas.notification_templates import (
    NotificationTemplateCreate,
    NotificationTemplatePreviewRequest,
    NotificationTemplatePreviewResponse,
    NotificationTemplateResponse,
    NotificationTemplateUpdate,
    NotificationTestRequest,
)
from api.security.notifications import (
    NotificationTemplateNotFoundError,
    create_notification_template,
    delete_notification_template,
    get_notification_template,
    list_notification_templates,
    preview_notification_template,
    send_test_notification,
    update_notification_template,
)
from api.security.permissions import require_permission

router = APIRouter(
    prefix="/organizations/{org_id}/notifications/templates",
    tags=["Notification Templates"],
)


@router.get("", response_model=list[NotificationTemplateResponse])
async def list_templates_endpoint(
    org_id: uuid.UUID,
    limit: int = Query(default=100, ge=1, le=500),
    offset: int = Query(default=0, ge=0),
    _caller: OrganizationMember = Depends(require_permission("settings:read")),
    db: AsyncSession = Depends(get_db),
):
    """List this org's own template overrides (does not include globals)."""
    return await list_notification_templates(db, org_id, limit=limit, offset=offset)


@router.post("", response_model=NotificationTemplateResponse, status_code=status.HTTP_201_CREATED)
async def create_template_endpoint(
    org_id: uuid.UUID,
    body: NotificationTemplateCreate,
    caller: OrganizationMember = Depends(require_permission("settings:manage")),
    db: AsyncSession = Depends(get_db),
):
    """Create an org-specific override. Fails 409 if this org already
    has a template for this notification_type."""
    try:
        tmpl = await create_notification_template(
            db, org_id, body.notification_type, body.title, body.body,
            email_subject=body.email_subject, is_active=body.is_active,
            created_by=caller.user_id,
        )
        await db.commit()
        return tmpl
    except IntegrityError:
        await db.rollback()
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=f"This organization already has a template for '{body.notification_type}'.",
        )


@router.get("/{template_id}", response_model=NotificationTemplateResponse)
async def get_template_endpoint(
    org_id: uuid.UUID,
    template_id: uuid.UUID,
    _caller: OrganizationMember = Depends(require_permission("settings:read")),
    db: AsyncSession = Depends(get_db),
):
    try:
        return await get_notification_template(db, org_id, template_id)
    except NotificationTemplateNotFoundError:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Template not found")


@router.patch("/{template_id}", response_model=NotificationTemplateResponse)
async def update_template_endpoint(
    org_id: uuid.UUID,
    template_id: uuid.UUID,
    body: NotificationTemplateUpdate,
    _caller: OrganizationMember = Depends(require_permission("settings:manage")),
    db: AsyncSession = Depends(get_db),
):
    try:
        tmpl = await update_notification_template(
            db, org_id, template_id,
            title=body.title, body=body.body,
            email_subject=body.email_subject, is_active=body.is_active,
        )
        await db.commit()
        return tmpl
    except NotificationTemplateNotFoundError:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Template not found")


@router.delete("/{template_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_template_endpoint(
    org_id: uuid.UUID,
    template_id: uuid.UUID,
    _caller: OrganizationMember = Depends(require_permission("settings:manage")),
    db: AsyncSession = Depends(get_db),
):
    try:
        await delete_notification_template(db, org_id, template_id)
        await db.commit()
    except NotificationTemplateNotFoundError:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Template not found")


@router.post("/preview", response_model=NotificationTemplatePreviewResponse)
async def preview_template_endpoint(
    org_id: uuid.UUID,
    body: NotificationTemplatePreviewRequest,
    _caller: OrganizationMember = Depends(require_permission("settings:read")),
    db: AsyncSession = Depends(get_db),
):
    """Render the effective template for this org+type with the given
    context, using the real DB-backed lookup (org-specific -> global ->
    code default). Never sends anything -- pure preview."""
    return await preview_notification_template(db, org_id, body.notification_type, body.context)


@router.post("/test", status_code=status.HTTP_202_ACCEPTED)
async def test_notification_endpoint(
    org_id: uuid.UUID,
    body: NotificationTestRequest,
    caller: OrganizationMember = Depends(require_permission("settings:manage")),
    db: AsyncSession = Depends(get_db),
):
    """Send a real test notification (in-app + email per preferences)
    to the calling user, using the given type + context. Useful to
    verify a customized template end-to-end without waiting for a real
    trigger."""
    await send_test_notification(db, org_id, caller.user_id, body.notification_type, body.context)
    await db.commit()
    return {"status": "sent"}
