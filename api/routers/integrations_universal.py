"""
Partie 15.1/15.2/15.3 -- universal inbound integrations + Airbyte.

Real deviation from the literal spec's flat `/integrations/...` and
`/automation/...` (two near-identical prompt batches describing the
same "receive a webhook, run an action" mechanism twice, under
different model names): consolidated into ONE real system here, and
routed under this codebase's established `/organizations/{org_id}/...`
convention for anything org-scoped -- same reasoning as billing.py's
own module docstring. The one exception, same as billing's Stripe
webhook, is the actual inbound receiver itself: an external system
(Zapier/n8n/a CRM) can't be asked to know an org_id ahead of time, so
`POST /integrations/inbound/{connection_id}` is flat and public,
authenticated by the connection's own bearer token instead.
"""

import uuid

from fastapi import APIRouter, Depends, HTTPException, Request, status
from sqlalchemy.ext.asyncio import AsyncSession

from api.dependencies import get_db
from api.models.integrations import AirbyteConnection
from api.models.organization import OrganizationMember
from api.schemas.integrations_universal import (
    AirbyteConnectionResponse, AirbyteCreateConnectionRequest, AirbyteCreateSourceRequest, AirbyteSourceDefinitionResponse,
    ConnectionCreateRequest, ConnectionCreateResponse, ConnectionResponse, ConnectionTestResponse, ConnectionUpdateRequest,
    LogResponse, MappingCreateRequest, MappingResponse, MappingUpdateRequest, ProviderResponse,
)
from api.security.organizations import require_org_admin, require_org_member
from api.services import airbyte_client, integrations

router = APIRouter(tags=["Integrations"])
org_router = APIRouter(prefix="/organizations/{org_id}/integrations", tags=["Integrations"])


@router.get("/integrations/n8n/status")
async def n8n_status_endpoint():
    """Real reachability check against a real n8n instance -- honest
    'reachable: false' rather than a fabricated 'ok' when N8N_URL is
    unset or the instance isn't actually up (e.g. the local Docker
    Compose n8n service, docker-compose.observability.yml, not
    started)."""
    from api.config import settings

    if not settings.N8N_URL:
        return {"configured": False, "reachable": False}
    try:
        import httpx

        async with httpx.AsyncClient(timeout=3.0) as client:
            response = await client.get(f"{settings.N8N_URL}/healthz")
        return {"configured": True, "reachable": response.status_code == 200, "url": settings.N8N_URL}
    except Exception:
        return {"configured": True, "reachable": False, "url": settings.N8N_URL}


@router.get("/integrations/airbyte/status")
async def airbyte_status_endpoint():
    from api.config import settings

    if not settings.AIRBYTE_API_URL:
        return {"configured": False, "reachable": False}
    try:
        await airbyte_client.list_source_definitions()
        return {"configured": True, "reachable": True, "url": settings.AIRBYTE_API_URL}
    except airbyte_client.AirbyteNotConfiguredError:
        return {"configured": False, "reachable": False}
    except Exception:
        return {"configured": True, "reachable": False, "url": settings.AIRBYTE_API_URL}


@router.get("/integrations/providers", response_model=list[ProviderResponse])
async def list_providers_endpoint():
    return integrations.list_integration_providers()


@org_router.get("/connections", response_model=list[ConnectionResponse])
async def list_connections_endpoint(org_id: uuid.UUID, _caller: OrganizationMember = Depends(require_org_member), db: AsyncSession = Depends(get_db)):
    return await integrations.list_connections(db, org_id)


@org_router.get("/connections/{connection_id}", response_model=ConnectionResponse)
async def get_connection_endpoint(org_id: uuid.UUID, connection_id: uuid.UUID, _caller: OrganizationMember = Depends(require_org_member), db: AsyncSession = Depends(get_db)):
    try:
        return await integrations.get_connection(db, org_id, connection_id)
    except integrations.ConnectionNotFoundError:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Connection not found")


@org_router.post("/connections", response_model=ConnectionCreateResponse, status_code=status.HTTP_201_CREATED)
async def create_connection_endpoint(org_id: uuid.UUID, body: ConnectionCreateRequest, caller: OrganizationMember = Depends(require_org_admin), db: AsyncSession = Depends(get_db)):
    connection, token = await integrations.create_connection(db, org_id, name=body.name, provider=body.provider, action=body.action, user_id=caller.user_id)
    await db.commit()
    return ConnectionCreateResponse(**ConnectionResponse.model_validate(connection).model_dump(), token=token)


@org_router.patch("/connections/{connection_id}", response_model=ConnectionResponse)
async def update_connection_endpoint(org_id: uuid.UUID, connection_id: uuid.UUID, body: ConnectionUpdateRequest, _caller: OrganizationMember = Depends(require_org_admin), db: AsyncSession = Depends(get_db)):
    try:
        connection = await integrations.update_connection(db, org_id, connection_id, **body.model_dump())
    except integrations.ConnectionNotFoundError:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Connection not found")
    await db.commit()
    return connection


@org_router.delete("/connections/{connection_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_connection_endpoint(org_id: uuid.UUID, connection_id: uuid.UUID, _caller: OrganizationMember = Depends(require_org_admin), db: AsyncSession = Depends(get_db)):
    try:
        await integrations.delete_connection(db, org_id, connection_id)
    except integrations.ConnectionNotFoundError:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Connection not found")
    await db.commit()


@org_router.get("/connections/{connection_id}/logs", response_model=list[LogResponse])
async def get_connection_logs_endpoint(org_id: uuid.UUID, connection_id: uuid.UUID, _caller: OrganizationMember = Depends(require_org_member), db: AsyncSession = Depends(get_db)):
    try:
        await integrations.get_connection(db, org_id, connection_id)
    except integrations.ConnectionNotFoundError:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Connection not found")
    return await integrations.get_logs(db, connection_id)


@org_router.post("/connections/{connection_id}/test", response_model=ConnectionTestResponse)
async def test_connection_endpoint(org_id: uuid.UUID, connection_id: uuid.UUID, _caller: OrganizationMember = Depends(require_org_admin), db: AsyncSession = Depends(get_db)):
    try:
        connection = await integrations.get_connection(db, org_id, connection_id)
    except integrations.ConnectionNotFoundError:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Connection not found")
    return await integrations.test_connection(db, connection)


@org_router.post("/connections/{connection_id}/sync", response_model=list[LogResponse])
async def sync_connection_endpoint(org_id: uuid.UUID, connection_id: uuid.UUID, _caller: OrganizationMember = Depends(require_org_admin), db: AsyncSession = Depends(get_db)):
    """Real, honest scope: this connection type is push-only (nothing
    external to pull from) -- 'sync' here means re-running the
    connection's current action against every previously FAILED
    payload (api/services/integrations.py's own docstring on why)."""
    try:
        connection = await integrations.get_connection(db, org_id, connection_id)
    except integrations.ConnectionNotFoundError:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Connection not found")
    results = await integrations.retry_failed_logs(db, connection)
    await db.commit()
    return results


@org_router.get("/connections/{connection_id}/syncs", response_model=list[LogResponse])
async def get_connection_syncs_endpoint(org_id: uuid.UUID, connection_id: uuid.UUID, _caller: OrganizationMember = Depends(require_org_member), db: AsyncSession = Depends(get_db)):
    """Real alias over this connection's own log ledger -- there is no
    separate 'sync run' concept for a push-only connection, see
    sync_connection_endpoint's own docstring."""
    try:
        await integrations.get_connection(db, org_id, connection_id)
    except integrations.ConnectionNotFoundError:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Connection not found")
    return await integrations.get_logs(db, connection_id)


@org_router.get("/connections/{connection_id}/mappings", response_model=list[MappingResponse])
async def list_mappings_endpoint(org_id: uuid.UUID, connection_id: uuid.UUID, _caller: OrganizationMember = Depends(require_org_member), db: AsyncSession = Depends(get_db)):
    try:
        await integrations.get_connection(db, org_id, connection_id)
    except integrations.ConnectionNotFoundError:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Connection not found")
    return await integrations.list_mappings(db, connection_id)


@org_router.post("/connections/{connection_id}/mappings", response_model=MappingResponse, status_code=status.HTTP_201_CREATED)
async def create_mapping_endpoint(org_id: uuid.UUID, connection_id: uuid.UUID, body: MappingCreateRequest, _caller: OrganizationMember = Depends(require_org_admin), db: AsyncSession = Depends(get_db)):
    try:
        await integrations.get_connection(db, org_id, connection_id)
    except integrations.ConnectionNotFoundError:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Connection not found")
    mapping = await integrations.create_mapping(db, connection_id, source_field=body.source_field, target_field=body.target_field, transform=body.transform)
    await db.commit()
    return mapping


@org_router.patch("/mappings/{mapping_id}", response_model=MappingResponse)
async def update_mapping_endpoint(org_id: uuid.UUID, mapping_id: uuid.UUID, body: MappingUpdateRequest, _caller: OrganizationMember = Depends(require_org_admin), db: AsyncSession = Depends(get_db)):
    try:
        mapping = await integrations.update_mapping(db, mapping_id, **body.model_dump())
    except integrations.MappingNotFoundError:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Mapping not found")
    await db.commit()
    return mapping


@org_router.delete("/mappings/{mapping_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_mapping_endpoint(org_id: uuid.UUID, mapping_id: uuid.UUID, _caller: OrganizationMember = Depends(require_org_admin), db: AsyncSession = Depends(get_db)):
    await integrations.delete_mapping(db, mapping_id)
    await db.commit()


# -- flat, public inbound receiver (Zapier/Make/n8n/any CRM webhook) ---------

@router.post("/integrations/inbound/{connection_id}", response_model=LogResponse)
async def inbound_webhook_endpoint(connection_id: uuid.UUID, request: Request, db: AsyncSession = Depends(get_db)):
    auth_header = request.headers.get("authorization", "")
    token = auth_header.removeprefix("Bearer ").strip()
    if not token:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Missing bearer token")

    connection = await integrations.find_connection_by_token(db, connection_id, token)
    if connection is None:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid or inactive connection token")

    try:
        payload = await request.json()
    except Exception:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Invalid JSON body")

    log = await integrations.handle_inbound_payload(db, connection, payload)
    await db.commit()
    return log


# -- 15.3 Airbyte (org-scoped) ------------------------------------------------

@org_router.get("/airbyte/source-definitions", response_model=list[AirbyteSourceDefinitionResponse])
async def list_airbyte_source_definitions_endpoint(org_id: uuid.UUID, _caller: OrganizationMember = Depends(require_org_member)):
    try:
        return await airbyte_client.list_source_definitions()
    except airbyte_client.AirbyteNotConfiguredError as exc:
        raise HTTPException(status_code=status.HTTP_501_NOT_IMPLEMENTED, detail=str(exc))


@org_router.get("/airbyte/connections", response_model=list[AirbyteConnectionResponse])
async def list_airbyte_connections_endpoint(org_id: uuid.UUID, _caller: OrganizationMember = Depends(require_org_member), db: AsyncSession = Depends(get_db)):
    return await airbyte_client.list_connections(db, org_id)


@org_router.post("/airbyte/sources", status_code=status.HTTP_201_CREATED)
async def create_airbyte_source_endpoint(org_id: uuid.UUID, body: AirbyteCreateSourceRequest, _caller: OrganizationMember = Depends(require_org_admin)):
    try:
        return await airbyte_client.create_source(name=body.name, source_definition_id=body.source_definition_id, connection_configuration=body.connection_configuration)
    except airbyte_client.AirbyteNotConfiguredError as exc:
        raise HTTPException(status_code=status.HTTP_501_NOT_IMPLEMENTED, detail=str(exc))


@org_router.get("/airbyte/sources/{source_id}/catalog")
async def get_airbyte_catalog_endpoint(org_id: uuid.UUID, source_id: str, _caller: OrganizationMember = Depends(require_org_member)):
    try:
        return await airbyte_client.get_source_catalog(source_id)
    except airbyte_client.AirbyteNotConfiguredError as exc:
        raise HTTPException(status_code=status.HTTP_501_NOT_IMPLEMENTED, detail=str(exc))


@org_router.post("/airbyte/connections", response_model=AirbyteConnectionResponse, status_code=status.HTTP_201_CREATED)
async def create_airbyte_connection_endpoint(org_id: uuid.UUID, body: AirbyteCreateConnectionRequest, caller: OrganizationMember = Depends(require_org_admin), db: AsyncSession = Depends(get_db)):
    try:
        result = await airbyte_client.create_connection(source_id=body.airbyte_source_id, destination_id=body.airbyte_destination_id, sync_catalog=body.sync_catalog)
    except airbyte_client.AirbyteNotConfiguredError as exc:
        raise HTTPException(status_code=status.HTTP_501_NOT_IMPLEMENTED, detail=str(exc))
    row = await airbyte_client.record_connection(db, org_id, name=body.name, airbyte_source_id=body.airbyte_source_id, airbyte_connection_id=result["connectionId"], source_type=body.source_type, user_id=caller.user_id)
    await db.commit()
    return row


@org_router.post("/airbyte/connections/{connection_id}/sync")
async def trigger_airbyte_sync_endpoint(org_id: uuid.UUID, connection_id: uuid.UUID, _caller: OrganizationMember = Depends(require_org_admin), db: AsyncSession = Depends(get_db)):
    row = await db.get(AirbyteConnection, connection_id)
    if row is None or row.organization_id != org_id:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Connection not found")
    try:
        return await airbyte_client.trigger_sync(row.airbyte_connection_id)
    except airbyte_client.AirbyteNotConfiguredError as exc:
        raise HTTPException(status_code=status.HTTP_501_NOT_IMPLEMENTED, detail=str(exc))
