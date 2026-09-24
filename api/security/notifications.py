"""Real security-layer service for NotificationTemplate CRUD + preview
+ test (P2 #6, session SSRF épinglé).

Every function here is org-scoped: a template id that belongs to a
different org is treated exactly like a missing one (404), never a
cross-tenant leak.
"""

import uuid

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from api.models.notification_template import NotificationTemplate


class NotificationTemplateNotFoundError(Exception):
    """Raised for a template id that does not exist OR belongs to a
    different org -- the two are deliberately indistinguishable so an
    attacker cannot probe for other orgs' template ids."""


async def list_notification_templates(
    db: AsyncSession, organization_id: uuid.UUID, *, limit: int = 100, offset: int = 0,
) -> list[NotificationTemplate]:
    stmt = (
        select(NotificationTemplate)
        .where(NotificationTemplate.organization_id == organization_id)
        .order_by(NotificationTemplate.notification_type)
        .limit(limit)
        .offset(offset)
    )
    return list((await db.scalars(stmt)).all())


async def get_notification_template(
    db: AsyncSession, organization_id: uuid.UUID, template_id: uuid.UUID,
) -> NotificationTemplate:
    row = await db.scalar(
        select(NotificationTemplate).where(
            NotificationTemplate.id == template_id,
            NotificationTemplate.organization_id == organization_id,
        )
    )
    if row is None:
        raise NotificationTemplateNotFoundError(str(template_id))
    return row


async def create_notification_template(
    db: AsyncSession, organization_id: uuid.UUID, notification_type: str,
    title: str, body: str, *, email_subject: str | None = None,
    is_active: bool = True, created_by: uuid.UUID | None = None,
) -> NotificationTemplate:
    row = NotificationTemplate(
        organization_id=organization_id,
        notification_type=notification_type,
        title=title,
        body=body,
        email_subject=email_subject,
        is_active=is_active,
        created_by=created_by,
    )
    db.add(row)
    await db.flush()
    return row


async def update_notification_template(
    db: AsyncSession, organization_id: uuid.UUID, template_id: uuid.UUID,
    *, title: str | None = None, body: str | None = None,
    email_subject: str | None = None, is_active: bool | None = None,
) -> NotificationTemplate:
    row = await get_notification_template(db, organization_id, template_id)
    if title is not None:
        row.title = title
    if body is not None:
        row.body = body
    if email_subject is not None:
        row.email_subject = email_subject
    if is_active is not None:
        row.is_active = is_active
    await db.flush()
    return row


async def delete_notification_template(
    db: AsyncSession, organization_id: uuid.UUID, template_id: uuid.UUID,
) -> None:
    row = await get_notification_template(db, organization_id, template_id)
    await db.delete(row)
    await db.flush()


async def preview_notification_template(
    db: AsyncSession, organization_id: uuid.UUID, notification_type: str, context: dict,
) -> dict:
    """Render the effective template (org-specific -> global -> code
    default) with the given context. Never sends anything."""
    from api.services.notification_templates import render_notification_from_db

    rendered = await render_notification_from_db(db, organization_id, notification_type, context)
    return {
        "title": rendered["title"],
        "body": rendered["body"],
        "email_subject": rendered.get("email_subject", rendered["title"]),
    }


async def send_test_notification(
    db: AsyncSession, organization_id: uuid.UUID, user_id: uuid.UUID,
    notification_type: str, context: dict,
) -> None:
    """Send a real notification to the calling user, using the given
    type + context. Reuses the real create_notification service so
    preferences, channels, branding, and persistence all match what a
    real trigger would produce."""
    from api.services.notifications import create_notification

    rendered = await preview_notification_template(db, organization_id, notification_type, context)
    await create_notification(
        db,
        user_id=user_id,
        organization_id=organization_id,
        type=notification_type,
        title=rendered["title"],
        body=rendered["body"],
        data=context,
    )
