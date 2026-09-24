"""
CRM import endpoints -- expose the Salesforce/HubSpot/Jira/Zendesk/
Pipedrive extraction modules (api/services/*_extraction.py) as real,
org-scoped API endpoints.

Each endpoint fetches records from the CRM and ingests them as real
documents into this organization's knowledge base, via the same
`upload_document` helper the other import endpoints (Notion, Google
Drive, etc.) already use.
"""

import logging
import uuid

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel
from sqlalchemy.ext.asyncio import AsyncSession

from api.config import settings
from api.dependencies import get_current_user, get_db
from api.models.organization import OrganizationMember
from api.models.user import User
from api.security.organizations import require_org_member
from api.security.permissions import require_permission

logger = logging.getLogger(__name__)

router = APIRouter(tags=["crm"])


class CRMImportRequest(BaseModel):
    limit: int = 100
    project_key: str | None = None  # Jira only


class CRMImportResponse(BaseModel):
    imported: int
    source: str
    status: str = "completed"


async def _ingest_records_as_documents(
    db: AsyncSession,
    org_id: uuid.UUID,
    user_id: uuid.UUID,
    source: str,
    records: list[dict],
) -> int:
    """Real: ingest each CRM record as a real document."""
    from api.security.documents import upload_document
    import datetime as dt

    count = 0
    for i, record in enumerate(records):
        text = record.get("text", "")
        if not text:
            continue
        record_id = record.get("id") or record.get("key") or str(i)
        filename = f"{source}-{record_id}-{dt.datetime.now(dt.timezone.utc).strftime('%Y%m%d%H%M%S')}.txt"
        try:
            await upload_document(db, org_id, None, user_id, filename, text.encode("utf-8"))
            count += 1
        except Exception as exc:
            logger.warning("Failed to ingest %s record %s: %s", source, record_id, exc)

    return count


@router.post("/organizations/{org_id}/crm/salesforce/import", response_model=CRMImportResponse)
async def import_salesforce(
    org_id: uuid.UUID,
    payload: CRMImportRequest,
    _caller: OrganizationMember = Depends(require_permission("documents:write")),
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    from api.services.salesforce_extraction import SalesforceError, fetch_salesforce_records
    if not settings.SALESFORCE_ENABLED:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Salesforce integration is disabled")
    try:
        records = await fetch_salesforce_records(limit=payload.limit)
    except SalesforceError as exc:
        raise HTTPException(status_code=status.HTTP_502_BAD_GATEWAY, detail=str(exc))
    count = await _ingest_records_as_documents(db, org_id, current_user.id, "salesforce", records)
    return CRMImportResponse(imported=count, source="salesforce")


@router.post("/organizations/{org_id}/crm/hubspot/import", response_model=CRMImportResponse)
async def import_hubspot(
    org_id: uuid.UUID,
    payload: CRMImportRequest,
    _caller: OrganizationMember = Depends(require_permission("documents:write")),
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    from api.services.hubspot_extraction import HubSpotError, fetch_hubspot_records
    if not settings.HUBSPOT_ENABLED:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="HubSpot integration is disabled")
    try:
        records = await fetch_hubspot_records(limit=payload.limit)
    except HubSpotError as exc:
        raise HTTPException(status_code=status.HTTP_502_BAD_GATEWAY, detail=str(exc))
    count = await _ingest_records_as_documents(db, org_id, current_user.id, "hubspot", records)
    return CRMImportResponse(imported=count, source="hubspot")


@router.post("/organizations/{org_id}/crm/jira/import", response_model=CRMImportResponse)
async def import_jira(
    org_id: uuid.UUID,
    payload: CRMImportRequest,
    _caller: OrganizationMember = Depends(require_permission("documents:write")),
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    from api.services.jira_extraction import JiraError, fetch_jira_issues
    if not settings.JIRA_ENABLED:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Jira integration is disabled")
    try:
        records = await fetch_jira_issues(project_key=payload.project_key, limit=payload.limit)
    except JiraError as exc:
        raise HTTPException(status_code=status.HTTP_502_BAD_GATEWAY, detail=str(exc))
    count = await _ingest_records_as_documents(db, org_id, current_user.id, "jira", records)
    return CRMImportResponse(imported=count, source="jira")


@router.post("/organizations/{org_id}/crm/zendesk/import", response_model=CRMImportResponse)
async def import_zendesk(
    org_id: uuid.UUID,
    payload: CRMImportRequest,
    _caller: OrganizationMember = Depends(require_permission("documents:write")),
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    from api.services.zendesk_extraction import ZendeskError, fetch_zendesk_tickets
    if not settings.ZENDESK_ENABLED:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Zendesk integration is disabled")
    try:
        records = await fetch_zendesk_tickets(limit=payload.limit)
    except ZendeskError as exc:
        raise HTTPException(status_code=status.HTTP_502_BAD_GATEWAY, detail=str(exc))
    count = await _ingest_records_as_documents(db, org_id, current_user.id, "zendesk", records)
    return CRMImportResponse(imported=count, source="zendesk")


@router.post("/organizations/{org_id}/crm/pipedrive/import", response_model=CRMImportResponse)
async def import_pipedrive(
    org_id: uuid.UUID,
    payload: CRMImportRequest,
    _caller: OrganizationMember = Depends(require_permission("documents:write")),
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    from api.services.pipedrive_extraction import PipedriveError, fetch_pipedrive_records
    if not settings.PIPEDRIVE_ENABLED:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Pipedrive integration is disabled")
    try:
        records = await fetch_pipedrive_records(limit=payload.limit)
    except PipedriveError as exc:
        raise HTTPException(status_code=status.HTTP_502_BAD_GATEWAY, detail=str(exc))
    count = await _ingest_records_as_documents(db, org_id, current_user.id, "pipedrive", records)
    return CRMImportResponse(imported=count, source="pipedrive")
