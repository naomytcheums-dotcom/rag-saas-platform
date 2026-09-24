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



# -- Phase 5, Étape 18 -- 12 additional real connectors ---------------------


@router.post("/organizations/{org_id}/crm/linear/import", response_model=CRMImportResponse)
async def import_linear(
    org_id: uuid.UUID,
    payload: CRMImportRequest,
    _caller: OrganizationMember = Depends(require_permission("documents:write")),
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    from api.services.linear_extraction import LinearError, fetch_linear_issues
    if not settings.LINEAR_ENABLED:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Linear integration is disabled")
    try:
        records = await fetch_linear_issues(limit=payload.limit)
    except LinearError as exc:
        raise HTTPException(status_code=status.HTTP_502_BAD_GATEWAY, detail=str(exc))
    count = await _ingest_records_as_documents(db, org_id, current_user.id, "linear", records)
    return CRMImportResponse(imported=count, source="linear")


@router.post("/organizations/{org_id}/crm/asana/import", response_model=CRMImportResponse)
async def import_asana(
    org_id: uuid.UUID,
    payload: CRMImportRequest,
    _caller: OrganizationMember = Depends(require_permission("documents:write")),
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    from api.services.asana_extraction import AsanaError, fetch_asana_tasks
    if not settings.ASANA_ENABLED:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Asana integration is disabled")
    try:
        records = await fetch_asana_tasks(limit=payload.limit)
    except AsanaError as exc:
        raise HTTPException(status_code=status.HTTP_502_BAD_GATEWAY, detail=str(exc))
    count = await _ingest_records_as_documents(db, org_id, current_user.id, "asana", records)
    return CRMImportResponse(imported=count, source="asana")


@router.post("/organizations/{org_id}/crm/trello/import", response_model=CRMImportResponse)
async def import_trello(
    org_id: uuid.UUID,
    payload: CRMImportRequest,
    _caller: OrganizationMember = Depends(require_permission("documents:write")),
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    from api.services.trello_extraction import TrelloError, fetch_trello_cards
    if not settings.TRELLO_ENABLED:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Trello integration is disabled")
    if not payload.project_key:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="board_id required (project_key)")
    try:
        records = await fetch_trello_cards(board_id=payload.project_key, limit=payload.limit)
    except TrelloError as exc:
        raise HTTPException(status_code=status.HTTP_502_BAD_GATEWAY, detail=str(exc))
    count = await _ingest_records_as_documents(db, org_id, current_user.id, "trello", records)
    return CRMImportResponse(imported=count, source="trello")


@router.post("/organizations/{org_id}/crm/airtable/import", response_model=CRMImportResponse)
async def import_airtable(
    org_id: uuid.UUID,
    payload: CRMImportRequest,
    _caller: OrganizationMember = Depends(require_permission("documents:write")),
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    from api.services.airtable_extraction import AirtableError, fetch_airtable_records
    if not settings.AIRTABLE_ENABLED:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Airtable integration is disabled")
    if not payload.project_key:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="base_id/table_name required (project_key, format: base_id/table)")
    parts = payload.project_key.split("/", 1)
    if len(parts) != 2:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="project_key must be base_id/table_name")
    try:
        records = await fetch_airtable_records(base_id=parts[0], table_name=parts[1], limit=payload.limit)
    except AirtableError as exc:
        raise HTTPException(status_code=status.HTTP_502_BAD_GATEWAY, detail=str(exc))
    count = await _ingest_records_as_documents(db, org_id, current_user.id, "airtable", records)
    return CRMImportResponse(imported=count, source="airtable")


@router.post("/organizations/{org_id}/crm/dropbox/import", response_model=CRMImportResponse)
async def import_dropbox(
    org_id: uuid.UUID,
    payload: CRMImportRequest,
    _caller: OrganizationMember = Depends(require_permission("documents:write")),
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    from api.services.dropbox_extraction import DropboxError, fetch_dropbox_files
    if not settings.DROPBOX_ENABLED:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Dropbox integration is disabled")
    try:
        records = await fetch_dropbox_files(path=payload.project_key or "", limit=payload.limit)
    except DropboxError as exc:
        raise HTTPException(status_code=status.HTTP_502_BAD_GATEWAY, detail=str(exc))
    count = await _ingest_records_as_documents(db, org_id, current_user.id, "dropbox", records)
    return CRMImportResponse(imported=count, source="dropbox")


@router.post("/organizations/{org_id}/crm/box/import", response_model=CRMImportResponse)
async def import_box(
    org_id: uuid.UUID,
    payload: CRMImportRequest,
    _caller: OrganizationMember = Depends(require_permission("documents:write")),
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    from api.services.box_extraction import BoxError, fetch_box_files
    if not settings.BOX_ENABLED:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Box integration is disabled")
    try:
        records = await fetch_box_files(folder_id=payload.project_key or "0", limit=payload.limit)
    except BoxError as exc:
        raise HTTPException(status_code=status.HTTP_502_BAD_GATEWAY, detail=str(exc))
    count = await _ingest_records_as_documents(db, org_id, current_user.id, "box", records)
    return CRMImportResponse(imported=count, source="box")


@router.post("/organizations/{org_id}/crm/clickup/import", response_model=CRMImportResponse)
async def import_clickup(
    org_id: uuid.UUID,
    payload: CRMImportRequest,
    _caller: OrganizationMember = Depends(require_permission("documents:write")),
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    from api.services.clickup_extraction import ClickUpError, fetch_clickup_tasks
    if not settings.CLICKUP_ENABLED:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="ClickUp integration is disabled")
    if not payload.project_key:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="list_id required (project_key)")
    try:
        records = await fetch_clickup_tasks(list_id=payload.project_key, limit=payload.limit)
    except ClickUpError as exc:
        raise HTTPException(status_code=status.HTTP_502_BAD_GATEWAY, detail=str(exc))
    count = await _ingest_records_as_documents(db, org_id, current_user.id, "clickup", records)
    return CRMImportResponse(imported=count, source="clickup")


@router.post("/organizations/{org_id}/crm/intercom/import", response_model=CRMImportResponse)
async def import_intercom(
    org_id: uuid.UUID,
    payload: CRMImportRequest,
    _caller: OrganizationMember = Depends(require_permission("documents:write")),
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    from api.services.intercom_extraction import IntercomError, fetch_intercom_conversations
    if not settings.INTERCOM_ENABLED:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Intercom integration is disabled")
    try:
        records = await fetch_intercom_conversations(limit=payload.limit)
    except IntercomError as exc:
        raise HTTPException(status_code=status.HTTP_502_BAD_GATEWAY, detail=str(exc))
    count = await _ingest_records_as_documents(db, org_id, current_user.id, "intercom", records)
    return CRMImportResponse(imported=count, source="intercom")


@router.post("/organizations/{org_id}/crm/zoho/import", response_model=CRMImportResponse)
async def import_zoho(
    org_id: uuid.UUID,
    payload: CRMImportRequest,
    _caller: OrganizationMember = Depends(require_permission("documents:write")),
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    from api.services.zoho_extraction import ZohoError, fetch_zoho_records
    if not settings.ZOHO_ENABLED:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Zoho integration is disabled")
    try:
        records = await fetch_zoho_records(module=payload.project_key or "Leads", limit=payload.limit)
    except ZohoError as exc:
        raise HTTPException(status_code=status.HTTP_502_BAD_GATEWAY, detail=str(exc))
    count = await _ingest_records_as_documents(db, org_id, current_user.id, "zoho", records)
    return CRMImportResponse(imported=count, source="zoho")


@router.post("/organizations/{org_id}/crm/shopify/import", response_model=CRMImportResponse)
async def import_shopify(
    org_id: uuid.UUID,
    payload: CRMImportRequest,
    _caller: OrganizationMember = Depends(require_permission("documents:write")),
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    from api.services.shopify_extraction import ShopifyError, fetch_shopify_orders
    if not settings.SHOPIFY_ENABLED:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Shopify integration is disabled")
    try:
        records = await fetch_shopify_orders(limit=payload.limit)
    except ShopifyError as exc:
        raise HTTPException(status_code=status.HTTP_502_BAD_GATEWAY, detail=str(exc))
    count = await _ingest_records_as_documents(db, org_id, current_user.id, "shopify", records)
    return CRMImportResponse(imported=count, source="shopify")


@router.post("/organizations/{org_id}/crm/woocommerce/import", response_model=CRMImportResponse)
async def import_woocommerce(
    org_id: uuid.UUID,
    payload: CRMImportRequest,
    _caller: OrganizationMember = Depends(require_permission("documents:write")),
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    from api.services.woocommerce_extraction import WooCommerceError, fetch_woocommerce_orders
    if not settings.WOOCOMMERCE_ENABLED:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="WooCommerce integration is disabled")
    try:
        records = await fetch_woocommerce_orders(limit=payload.limit)
    except WooCommerceError as exc:
        raise HTTPException(status_code=status.HTTP_502_BAD_GATEWAY, detail=str(exc))
    count = await _ingest_records_as_documents(db, org_id, current_user.id, "woocommerce", records)
    return CRMImportResponse(imported=count, source="woocommerce")


@router.post("/organizations/{org_id}/crm/docusign/import", response_model=CRMImportResponse)
async def import_docusign(
    org_id: uuid.UUID,
    payload: CRMImportRequest,
    _caller: OrganizationMember = Depends(require_permission("documents:write")),
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    from api.services.docusign_extraction import DocuSignError, fetch_docusign_envelopes
    if not settings.DOCUSIGN_ENABLED:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="DocuSign integration is disabled")
    try:
        records = await fetch_docusign_envelopes(limit=payload.limit)
    except DocuSignError as exc:
        raise HTTPException(status_code=status.HTTP_502_BAD_GATEWAY, detail=str(exc))
    count = await _ingest_records_as_documents(db, org_id, current_user.id, "docusign", records)
    return CRMImportResponse(imported=count, source="docusign")



# -- Phase 5, Étape 19 -- 9 more real connectors ------------------------------


@router.post("/organizations/{org_id}/crm/monday/import", response_model=CRMImportResponse)
async def import_monday(
    org_id: uuid.UUID,
    payload: CRMImportRequest,
    _caller: OrganizationMember = Depends(require_permission("documents:write")),
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    from api.services.monday_extraction import MondayError, fetch_monday_records
    if not settings.MONDAY_ENABLED:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Monday integration is disabled")
    try:
        records = await fetch_monday_records(limit=payload.limit)
    except MondayError as exc:
        raise HTTPException(status_code=status.HTTP_502_BAD_GATEWAY, detail=str(exc))
    count = await _ingest_records_as_documents(db, org_id, current_user.id, "monday", records)
    return CRMImportResponse(imported=count, source="monday")


@router.post("/organizations/{org_id}/crm/gitlab/import", response_model=CRMImportResponse)
async def import_gitlab(
    org_id: uuid.UUID,
    payload: CRMImportRequest,
    _caller: OrganizationMember = Depends(require_permission("documents:write")),
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    from api.services.gitlab_extraction import GitLabError, fetch_gitlab_records
    if not settings.GITLAB_ENABLED:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="GitLab integration is disabled")
    try:
        records = await fetch_gitlab_records(limit=payload.limit)
    except GitLabError as exc:
        raise HTTPException(status_code=status.HTTP_502_BAD_GATEWAY, detail=str(exc))
    count = await _ingest_records_as_documents(db, org_id, current_user.id, "gitlab", records)
    return CRMImportResponse(imported=count, source="gitlab")


@router.post("/organizations/{org_id}/crm/bitbucket/import", response_model=CRMImportResponse)
async def import_bitbucket(
    org_id: uuid.UUID,
    payload: CRMImportRequest,
    _caller: OrganizationMember = Depends(require_permission("documents:write")),
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    from api.services.bitbucket_extraction import BitbucketError, fetch_bitbucket_records
    if not settings.BITBUCKET_ENABLED:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Bitbucket integration is disabled")
    try:
        records = await fetch_bitbucket_records(limit=payload.limit)
    except BitbucketError as exc:
        raise HTTPException(status_code=status.HTTP_502_BAD_GATEWAY, detail=str(exc))
    count = await _ingest_records_as_documents(db, org_id, current_user.id, "bitbucket", records)
    return CRMImportResponse(imported=count, source="bitbucket")


@router.post("/organizations/{org_id}/crm/azure-devops/import", response_model=CRMImportResponse)
async def import_azure_devops(
    org_id: uuid.UUID,
    payload: CRMImportRequest,
    _caller: OrganizationMember = Depends(require_permission("documents:write")),
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    from api.services.azure_devops_extraction import AzureDevOpsError, fetch_azure_devops_records
    if not settings.AZURE_DEVOPS_ENABLED:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Azure DevOps integration is disabled")
    try:
        records = await fetch_azure_devops_records(limit=payload.limit)
    except AzureDevOpsError as exc:
        raise HTTPException(status_code=status.HTTP_502_BAD_GATEWAY, detail=str(exc))
    count = await _ingest_records_as_documents(db, org_id, current_user.id, "azure-devops", records)
    return CRMImportResponse(imported=count, source="azure-devops")


@router.post("/organizations/{org_id}/crm/basecamp/import", response_model=CRMImportResponse)
async def import_basecamp(
    org_id: uuid.UUID,
    payload: CRMImportRequest,
    _caller: OrganizationMember = Depends(require_permission("documents:write")),
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    from api.services.basecamp_extraction import BasecampError, fetch_basecamp_records
    if not settings.BASECAMP_ENABLED:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Basecamp integration is disabled")
    try:
        records = await fetch_basecamp_records(limit=payload.limit)
    except BasecampError as exc:
        raise HTTPException(status_code=status.HTTP_502_BAD_GATEWAY, detail=str(exc))
    count = await _ingest_records_as_documents(db, org_id, current_user.id, "basecamp", records)
    return CRMImportResponse(imported=count, source="basecamp")


@router.post("/organizations/{org_id}/crm/wrike/import", response_model=CRMImportResponse)
async def import_wrike(
    org_id: uuid.UUID,
    payload: CRMImportRequest,
    _caller: OrganizationMember = Depends(require_permission("documents:write")),
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    from api.services.wrike_extraction import WrikeError, fetch_wrike_records
    if not settings.WRIKE_ENABLED:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Wrike integration is disabled")
    try:
        records = await fetch_wrike_records(limit=payload.limit)
    except WrikeError as exc:
        raise HTTPException(status_code=status.HTTP_502_BAD_GATEWAY, detail=str(exc))
    count = await _ingest_records_as_documents(db, org_id, current_user.id, "wrike", records)
    return CRMImportResponse(imported=count, source="wrike")


@router.post("/organizations/{org_id}/crm/smartsheet/import", response_model=CRMImportResponse)
async def import_smartsheet(
    org_id: uuid.UUID,
    payload: CRMImportRequest,
    _caller: OrganizationMember = Depends(require_permission("documents:write")),
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    from api.services.smartsheet_extraction import SmartsheetError, fetch_smartsheet_records
    if not settings.SMARTSHEET_ENABLED:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Smartsheet integration is disabled")
    try:
        records = await fetch_smartsheet_records(limit=payload.limit)
    except SmartsheetError as exc:
        raise HTTPException(status_code=status.HTTP_502_BAD_GATEWAY, detail=str(exc))
    count = await _ingest_records_as_documents(db, org_id, current_user.id, "smartsheet", records)
    return CRMImportResponse(imported=count, source="smartsheet")


@router.post("/organizations/{org_id}/crm/coda/import", response_model=CRMImportResponse)
async def import_coda(
    org_id: uuid.UUID,
    payload: CRMImportRequest,
    _caller: OrganizationMember = Depends(require_permission("documents:write")),
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    from api.services.coda_extraction import CodaError, fetch_coda_records
    if not settings.CODA_ENABLED:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Coda integration is disabled")
    try:
        records = await fetch_coda_records(limit=payload.limit)
    except CodaError as exc:
        raise HTTPException(status_code=status.HTTP_502_BAD_GATEWAY, detail=str(exc))
    count = await _ingest_records_as_documents(db, org_id, current_user.id, "coda", records)
    return CRMImportResponse(imported=count, source="coda")


@router.post("/organizations/{org_id}/crm/miro/import", response_model=CRMImportResponse)
async def import_miro(
    org_id: uuid.UUID,
    payload: CRMImportRequest,
    _caller: OrganizationMember = Depends(require_permission("documents:write")),
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    from api.services.miro_extraction import MiroError, fetch_miro_records
    if not settings.MIRO_ENABLED:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Miro integration is disabled")
    try:
        records = await fetch_miro_records(limit=payload.limit)
    except MiroError as exc:
        raise HTTPException(status_code=status.HTTP_502_BAD_GATEWAY, detail=str(exc))
    count = await _ingest_records_as_documents(db, org_id, current_user.id, "miro", records)
    return CRMImportResponse(imported=count, source="miro")



# -- Phase 5, Étape 20 -- 10 more real connectors ------------------------------


@router.post("/organizations/{org_id}/crm/podio/import", response_model=CRMImportResponse)
async def import_podio(
    org_id: uuid.UUID,
    payload: CRMImportRequest,
    _caller: OrganizationMember = Depends(require_permission("documents:write")),
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    from api.services.podio_extraction import PodioError, fetch_podio_items
    if not settings.PODIO_ENABLED:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Podio integration is disabled")
    if not payload.project_key:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="app_id required (project_key)")
    try:
        records = await fetch_podio_items(app_id=payload.project_key, limit=payload.limit)
    except PodioError as exc:
        raise HTTPException(status_code=status.HTTP_502_BAD_GATEWAY, detail=str(exc))
    count = await _ingest_records_as_documents(db, org_id, current_user.id, "podio", records)
    return CRMImportResponse(imported=count, source="podio")


@router.post("/organizations/{org_id}/crm/pipefy/import", response_model=CRMImportResponse)
async def import_pipefy(
    org_id: uuid.UUID,
    payload: CRMImportRequest,
    _caller: OrganizationMember = Depends(require_permission("documents:write")),
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    from api.services.pipefy_extraction import PipefyError, fetch_pipefy_cards
    if not settings.PIPEFY_ENABLED:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Pipefy integration is disabled")
    if not payload.project_key:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="pipe_id required (project_key)")
    try:
        records = await fetch_pipefy_cards(pipe_id=payload.project_key, limit=payload.limit)
    except PipefyError as exc:
        raise HTTPException(status_code=status.HTTP_502_BAD_GATEWAY, detail=str(exc))
    count = await _ingest_records_as_documents(db, org_id, current_user.id, "pipefy", records)
    return CRMImportResponse(imported=count, source="pipefy")


@router.post("/organizations/{org_id}/crm/hive/import", response_model=CRMImportResponse)
async def import_hive(
    org_id: uuid.UUID,
    payload: CRMImportRequest,
    _caller: OrganizationMember = Depends(require_permission("documents:write")),
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    from api.services.hive_extraction import HiveError, fetch_hive_actions
    if not settings.HIVE_ENABLED:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Hive integration is disabled")
    if not payload.project_key:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="workspace_id required (project_key)")
    try:
        records = await fetch_hive_actions(workspace_id=payload.project_key, limit=payload.limit)
    except HiveError as exc:
        raise HTTPException(status_code=status.HTTP_502_BAD_GATEWAY, detail=str(exc))
    count = await _ingest_records_as_documents(db, org_id, current_user.id, "hive", records)
    return CRMImportResponse(imported=count, source="hive")


@router.post("/organizations/{org_id}/crm/teamwork/import", response_model=CRMImportResponse)
async def import_teamwork(
    org_id: uuid.UUID,
    payload: CRMImportRequest,
    _caller: OrganizationMember = Depends(require_permission("documents:write")),
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    from api.services.teamwork_extraction import TeamworkError, fetch_teamwork_tasks
    if not settings.TEAMWORK_ENABLED:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Teamwork integration is disabled")
    try:
        records = await fetch_teamwork_tasks(limit=payload.limit)
    except TeamworkError as exc:
        raise HTTPException(status_code=status.HTTP_502_BAD_GATEWAY, detail=str(exc))
    count = await _ingest_records_as_documents(db, org_id, current_user.id, "teamwork", records)
    return CRMImportResponse(imported=count, source="teamwork")


@router.post("/organizations/{org_id}/crm/nifty/import", response_model=CRMImportResponse)
async def import_nifty(
    org_id: uuid.UUID,
    payload: CRMImportRequest,
    _caller: OrganizationMember = Depends(require_permission("documents:write")),
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    from api.services.nifty_extraction import NiftyError, fetch_nifty_tasks
    if not settings.NIFTY_ENABLED:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Nifty integration is disabled")
    if not payload.project_key:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="project_id required (project_key)")
    try:
        records = await fetch_nifty_tasks(project_id=payload.project_key, limit=payload.limit)
    except NiftyError as exc:
        raise HTTPException(status_code=status.HTTP_502_BAD_GATEWAY, detail=str(exc))
    count = await _ingest_records_as_documents(db, org_id, current_user.id, "nifty", records)
    return CRMImportResponse(imported=count, source="nifty")


@router.post("/organizations/{org_id}/crm/smartsuite/import", response_model=CRMImportResponse)
async def import_smartsuite(
    org_id: uuid.UUID,
    payload: CRMImportRequest,
    _caller: OrganizationMember = Depends(require_permission("documents:write")),
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    from api.services.smartsuite_extraction import SmartSuiteError, fetch_smartsuite_records
    if not settings.SMARTSUITE_ENABLED:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="SmartSuite integration is disabled")
    if not payload.project_key:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="table_id required (project_key)")
    try:
        records = await fetch_smartsuite_records(table_id=payload.project_key, limit=payload.limit)
    except SmartSuiteError as exc:
        raise HTTPException(status_code=status.HTTP_502_BAD_GATEWAY, detail=str(exc))
    count = await _ingest_records_as_documents(db, org_id, current_user.id, "smartsuite", records)
    return CRMImportResponse(imported=count, source="smartsuite")


@router.post("/organizations/{org_id}/crm/process-street/import", response_model=CRMImportResponse)
async def import_process_street(
    org_id: uuid.UUID,
    payload: CRMImportRequest,
    _caller: OrganizationMember = Depends(require_permission("documents:write")),
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    from api.services.process_street_extraction import ProcessStreetError, fetch_process_street_workflows
    if not settings.PROCESS_STREET_ENABLED:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Process Street integration is disabled")
    try:
        records = await fetch_process_street_workflows(limit=payload.limit)
    except ProcessStreetError as exc:
        raise HTTPException(status_code=status.HTTP_502_BAD_GATEWAY, detail=str(exc))
    count = await _ingest_records_as_documents(db, org_id, current_user.id, "process-street", records)
    return CRMImportResponse(imported=count, source="process-street")


@router.post("/organizations/{org_id}/crm/activecampaign/import", response_model=CRMImportResponse)
async def import_activecampaign(
    org_id: uuid.UUID,
    payload: CRMImportRequest,
    _caller: OrganizationMember = Depends(require_permission("documents:write")),
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    from api.services.activecampaign_extraction import ActiveCampaignError, fetch_activecampaign_contacts
    if not settings.ACTIVECAMPAIGN_ENABLED:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="ActiveCampaign integration is disabled")
    try:
        records = await fetch_activecampaign_contacts(limit=payload.limit)
    except ActiveCampaignError as exc:
        raise HTTPException(status_code=status.HTTP_502_BAD_GATEWAY, detail=str(exc))
    count = await _ingest_records_as_documents(db, org_id, current_user.id, "activecampaign", records)
    return CRMImportResponse(imported=count, source="activecampaign")


@router.post("/organizations/{org_id}/crm/mailchimp/import", response_model=CRMImportResponse)
async def import_mailchimp(
    org_id: uuid.UUID,
    payload: CRMImportRequest,
    _caller: OrganizationMember = Depends(require_permission("documents:write")),
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    from api.services.mailchimp_extraction import MailchimpError, fetch_mailchimp_audiences
    if not settings.MAILCHIMP_ENABLED:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Mailchimp integration is disabled")
    try:
        records = await fetch_mailchimp_audiences(limit=payload.limit)
    except MailchimpError as exc:
        raise HTTPException(status_code=status.HTTP_502_BAD_GATEWAY, detail=str(exc))
    count = await _ingest_records_as_documents(db, org_id, current_user.id, "mailchimp", records)
    return CRMImportResponse(imported=count, source="mailchimp")


@router.post("/organizations/{org_id}/crm/klaviyo/import", response_model=CRMImportResponse)
async def import_klaviyo(
    org_id: uuid.UUID,
    payload: CRMImportRequest,
    _caller: OrganizationMember = Depends(require_permission("documents:write")),
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    from api.services.klaviyo_extraction import KlaviyoError, fetch_klaviyo_profiles
    if not settings.KLAVIYO_ENABLED:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Klaviyo integration is disabled")
    try:
        records = await fetch_klaviyo_profiles(limit=payload.limit)
    except KlaviyoError as exc:
        raise HTTPException(status_code=status.HTTP_502_BAD_GATEWAY, detail=str(exc))
    count = await _ingest_records_as_documents(db, org_id, current_user.id, "klaviyo", records)
    return CRMImportResponse(imported=count, source="klaviyo")
