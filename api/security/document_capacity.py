"""Specs 1.3.6 / 12.3.2 / 12.3.3 -- document count and storage limits on EVERY way of adding documents.

Before this module only the single-file upload checked the plan's document limit; the batch upload and the nine importers (URL, sitemap, GitHub, Google
Drive/Docs, Notion, Confluence, OneDrive) added documents without any check, and the storage quota stored on `OrganizationQuota.max_storage_mb` was never
enforced. `require_document_capacity` is a route dependency for the importers; `require_storage_available` checks the bytes of an upload.
Both answer 402 with a message the user can act on."""

import uuid

from fastapi import Depends, HTTPException, status
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from api.database import get_db
from api.models.document import Document
from api.models.organization import OrganizationMember
from api.models.organization_quota import OrganizationQuota
from api.security.permissions import require_permission
from api.services.billing_usage import check_plan_resource_limit

_MB = 1024 * 1024


async def require_document_capacity(
    org_id: uuid.UUID, _caller: OrganizationMember = Depends(require_permission("documents:write")), db: AsyncSession = Depends(get_db),
) -> None:
    """Refuse an import when the plan's document limit is already reached (one more document would not fit). Depends on the write permission so that
    a non-member never learns anything about the organization's plan from this answer."""
    within_limit, count, limit = await check_plan_resource_limit(db, org_id, "documents")
    if not within_limit:
        raise HTTPException(
            status_code=status.HTTP_402_PAYMENT_REQUIRED,
            detail=f"This organization's plan allows {limit} documents (currently {count}). Upgrade the plan to add more.",
        )


async def require_batch_capacity(db: AsyncSession, org_id: uuid.UUID, additional: int) -> None:
    """Same limit for a batch of `additional` files: the whole batch must fit."""
    _within, count, limit = await check_plan_resource_limit(db, org_id, "documents")
    if limit is not None and (count or 0) + additional > limit:
        raise HTTPException(
            status_code=status.HTTP_402_PAYMENT_REQUIRED,
            detail=f"This organization's plan allows {limit} documents (currently {count}); {additional} more would exceed it. Upgrade the plan or upload fewer files.",
        )


async def storage_used_bytes(db: AsyncSession, org_id: uuid.UUID) -> int:
    return int(await db.scalar(select(func.coalesce(func.sum(Document.file_size), 0)).where(Document.organization_id == org_id, Document.deleted_at.is_(None))) or 0)


async def require_storage_available(db: AsyncSession, org_id: uuid.UUID, additional_bytes: int) -> None:
    """Refuse an upload that would take the organization above its storage quota (`OrganizationQuota.max_storage_mb`; no row = no limit)."""
    quota = await db.scalar(select(OrganizationQuota).where(OrganizationQuota.organization_id == org_id))
    if quota is None or not isinstance(quota.max_storage_mb, int):
        return
    used = await storage_used_bytes(db, org_id)
    if used + additional_bytes > quota.max_storage_mb * _MB:
        raise HTTPException(
            status_code=status.HTTP_402_PAYMENT_REQUIRED,
            detail=f"Storage quota exceeded: {quota.max_storage_mb} MB allowed, {used // _MB} MB used. Delete documents or ask your organization owner to raise the quota.",
        )
