"""Per-organization credentials for the importers and CRM connectors (docs/DECISIONS.md D17).

  GET    /organizations/{org_id}/connectors            which connectors this organization has connected (never the secrets)
  PUT    /organizations/{org_id}/connectors/{provider} store (replace) the organization's credentials, encrypted
  DELETE /organizations/{org_id}/connectors/{provider} remove them

Reading needs `integrations:read`, writing `integrations:write`. A secret is never sent back; the list only names the fields that are set."""

import datetime as dt
import uuid

from fastapi import APIRouter, Depends, HTTPException, Request, Response, status
from pydantic import BaseModel, Field
from sqlalchemy.ext.asyncio import AsyncSession

from api.config import settings
from api.dependencies import get_current_user, get_db
from api.models.audit_log import AuditAction
from api.models.organization import OrganizationMember
from api.models.user import User
from api.security.audit_log import log_audit_action
from api.security.encryption import EncryptionNotConfiguredError, decrypt_data
from api.security.permissions import require_permission
from api.services.connector_credentials import (
    OPTIONAL_CREDENTIALS, PROVIDERS, connected_providers, delete_credentials, normalize_provider, save_credentials, validate_credentials,
)
from api.utils import client_ip

router = APIRouter(tags=["connectors"])


class ConnectorOut(BaseModel):
    provider: str
    connected: bool
    fields_set: list[str]
    required_fields: list[str]
    optional_fields: list[str]
    works_without_credentials: bool
    updated_at: dt.datetime | None = None


class ConnectorListOut(BaseModel):
    connectors: list[ConnectorOut]
    platform_credentials_allowed: bool


class ConnectorIn(BaseModel):
    fields: dict[str, str] = Field(min_length=1, max_length=20)


def _describe(provider: str, row) -> ConnectorOut:
    import json

    fields_set: list[str] = []
    if row is not None:
        try:
            fields_set = sorted(json.loads(decrypt_data(row.encrypted_payload)))
        except Exception:  # noqa: BLE001 -- an undecryptable payload (key rotated away) is reported as not usable, never as an error page
            fields_set = []
    return ConnectorOut(
        provider=provider, connected=bool(fields_set), fields_set=fields_set,
        required_fields=[f.name for f in PROVIDERS[provider] if f.required], optional_fields=[f.name for f in PROVIDERS[provider] if not f.required],
        works_without_credentials=provider in OPTIONAL_CREDENTIALS, updated_at=row.updated_at if row is not None else None,
    )


@router.get("/organizations/{org_id}/connectors", response_model=ConnectorListOut)
async def list_connectors(
    org_id: uuid.UUID, _caller: OrganizationMember = Depends(require_permission("integrations:read")), db: AsyncSession = Depends(get_db),
):
    rows = await connected_providers(db, org_id)
    return ConnectorListOut(
        connectors=[_describe(provider, rows.get(provider)) for provider in sorted(PROVIDERS)],
        platform_credentials_allowed=settings.CONNECTORS_ALLOW_PLATFORM_CREDENTIALS,
    )


@router.put("/organizations/{org_id}/connectors/{provider}", response_model=ConnectorOut)
async def put_connector(
    org_id: uuid.UUID, provider: str, payload: ConnectorIn, request: Request,
    _caller: OrganizationMember = Depends(require_permission("integrations:write")),
    current_user: User = Depends(get_current_user), db: AsyncSession = Depends(get_db),
):
    provider = normalize_provider(provider)
    try:
        values = validate_credentials(provider, payload.fields)
    except ValueError as exc:
        raise HTTPException(status.HTTP_422_UNPROCESSABLE_ENTITY, str(exc)) from exc
    try:
        row = await save_credentials(db, org_id, provider, values, current_user.id)
    except EncryptionNotConfiguredError as exc:
        raise HTTPException(status.HTTP_503_SERVICE_UNAVAILABLE, "Credentials cannot be stored: ENCRYPTION_MASTER_KEY is not configured on the server.") from exc
    await log_audit_action(
        db, user_id=current_user.id, action=AuditAction.INTEGRATION_CONNECTED, ip=client_ip(request), user_agent=request.headers.get("user-agent"),
        success=True, metadata={"provider": provider, "fields": sorted(values)}, organization_id=org_id, resource_type="connector", resource_id=provider,
    )
    await db.commit()
    return _describe(provider, row)


@router.delete("/organizations/{org_id}/connectors/{provider}", status_code=status.HTTP_204_NO_CONTENT)
async def remove_connector(
    org_id: uuid.UUID, provider: str, request: Request,
    _caller: OrganizationMember = Depends(require_permission("integrations:write")),
    current_user: User = Depends(get_current_user), db: AsyncSession = Depends(get_db),
):
    provider = normalize_provider(provider)
    if not await delete_credentials(db, org_id, provider):
        raise HTTPException(status.HTTP_404_NOT_FOUND, f"No {provider} credentials stored for this organization")
    await log_audit_action(
        db, user_id=current_user.id, action=AuditAction.INTEGRATION_DISCONNECTED, ip=client_ip(request), user_agent=request.headers.get("user-agent"),
        success=True, metadata={"provider": provider}, organization_id=org_id, resource_type="connector", resource_id=provider,
    )
    await db.commit()
    return Response(status_code=status.HTTP_204_NO_CONTENT)
