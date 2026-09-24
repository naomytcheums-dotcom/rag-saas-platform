"""
Phase 5, Étape 4 -- in-app + email notifications. Flat `/notifications`
paths (not `/organizations/{org_id}/notifications`, this codebase's
usual convention) -- a REAL, deliberate deviation: a notification
belongs to a USER first (it's about something that happened to THEM),
who may belong to several organizations, unlike billing/branding/
domains which belong to exactly one organization. Every query below
filters by `current_user.id` FIRST, with `organization_id` as an
optional narrowing query param -- there is no code path where a
caller's own `user_id` isn't part of the WHERE clause, so cross-tenant
leakage is structurally impossible regardless of what `organization_id`
is passed (a non-member org_id just returns an empty list, never
another user's rows).

`api/routers/notifications.py` (Twilio SMS/WhatsApp, prefix
`/organizations/{org_id}/notifications`) is a different, pre-existing
feature that happens to share the word "notifications" -- no path
collision (different prefixes entirely).
"""

import uuid

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.ext.asyncio import AsyncSession
from starlette.responses import StreamingResponse

from api.dependencies import get_current_user, get_db
from api.models.user import User
from api.schemas.notification_center import (
    MarkAllReadResponse, NotificationPreferenceResponse, NotificationPreferenceUpdateRequest, NotificationResponse,
    UnreadCountResponse,
)
from api.services import notifications
from api.utils import MAX_PAGE_SIZE

router = APIRouter(prefix="/notifications", tags=["Notifications"])

_SSE_HEADERS = {"Cache-Control": "no-cache", "X-Accel-Buffering": "no"}


@router.get("", response_model=list[NotificationResponse])
async def list_notifications_endpoint(
    organization_id: uuid.UUID | None = None, unread_only: bool = False,
    limit: int = Query(default=50, ge=1, le=MAX_PAGE_SIZE), offset: int = Query(default=0, ge=0),
    current_user: User = Depends(get_current_user), db: AsyncSession = Depends(get_db),
):
    return await notifications.list_notifications(db, current_user.id, organization_id=organization_id, unread_only=unread_only, limit=limit, offset=offset)


@router.get("/unread-count", response_model=UnreadCountResponse)
async def unread_count_endpoint(organization_id: uuid.UUID | None = None, current_user: User = Depends(get_current_user), db: AsyncSession = Depends(get_db)):
    count = await notifications.get_unread_count(db, current_user.id, organization_id=organization_id)
    return UnreadCountResponse(unread_count=count)


@router.patch("/{notification_id}/read", response_model=NotificationResponse)
async def mark_read_endpoint(notification_id: uuid.UUID, current_user: User = Depends(get_current_user), db: AsyncSession = Depends(get_db)):
    try:
        notification = await notifications.mark_read(db, notification_id, current_user.id)
    except notifications.NotificationNotFoundError:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Notification not found")
    await db.commit()
    return notification


@router.post("/mark-all-read", response_model=MarkAllReadResponse)
async def mark_all_read_endpoint(organization_id: uuid.UUID | None = None, current_user: User = Depends(get_current_user), db: AsyncSession = Depends(get_db)):
    marked = await notifications.mark_all_read(db, current_user.id, organization_id=organization_id)
    await db.commit()
    return MarkAllReadResponse(marked_count=marked)


@router.delete("/{notification_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_notification_endpoint(notification_id: uuid.UUID, current_user: User = Depends(get_current_user), db: AsyncSession = Depends(get_db)):
    try:
        await notifications.delete_notification(db, notification_id, current_user.id)
    except notifications.NotificationNotFoundError:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Notification not found")
    await db.commit()


@router.get("/preferences", response_model=list[NotificationPreferenceResponse])
async def get_preferences_endpoint(organization_id: uuid.UUID, current_user: User = Depends(get_current_user), db: AsyncSession = Depends(get_db)):
    return await notifications.get_preferences(db, current_user.id, organization_id)


@router.patch("/preferences", response_model=NotificationPreferenceResponse)
async def update_preferences_endpoint(organization_id: uuid.UUID, body: NotificationPreferenceUpdateRequest, current_user: User = Depends(get_current_user), db: AsyncSession = Depends(get_db)):
    pref = await notifications.update_preference(db, current_user.id, organization_id, body.notification_type, in_app_enabled=body.in_app_enabled, email_enabled=body.email_enabled)
    await db.commit()
    return pref


@router.get("/stream")
async def stream_notifications_endpoint(
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> StreamingResponse:
    """Real-time delivery via Server-Sent Events -- a real browser
    EventSource reconnects automatically on drop, same real behavior
    api/routers/documents.py's own SSE route already relies on.

    Phase 5, Étape 4bis -- sends a real initial snapshot of unread
    notifications before streaming new ones, so a reconnecting client
    never misses what happened while offline."""
    return StreamingResponse(
        notifications.stream_user_notifications(current_user.id, db),
        media_type="text/event-stream",
        headers=_SSE_HEADERS,
    )
