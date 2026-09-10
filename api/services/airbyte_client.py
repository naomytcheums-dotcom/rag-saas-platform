"""
Partie 15.3 -- real Airbyte integration. Airbyte itself is what
provides the 300+ real source connectors (Salesforce, HubSpot, SAP,
Postgres, ...) -- this module calls a REAL Airbyte instance's own
public REST API (Airbyte OSS/Cloud, `/api/v1/...`) to create sources,
connections, and trigger syncs, rather than reimplementing any
connector logic ourselves. Honest scope, same pattern as
api/services/billing_stripe.py: `AIRBYTE_API_URL`/`AIRBYTE_API_KEY` are
unset in this environment (no real Airbyte instance is deployed here),
so every function raises AirbyteNotConfiguredError -> a real 501,
never a fabricated success.
"""

import uuid

import httpx
from sqlalchemy.ext.asyncio import AsyncSession

from api.config import settings
from api.models.integrations import AirbyteConnection


class AirbyteNotConfiguredError(Exception):
    pass


def _client() -> httpx.AsyncClient:
    if not settings.AIRBYTE_API_URL or not settings.AIRBYTE_API_KEY:
        raise AirbyteNotConfiguredError(
            "Airbyte is not configured on this deployment -- set AIRBYTE_API_URL and AIRBYTE_API_KEY in .env "
            "(point them at a real Airbyte OSS or Cloud instance) to enable real source connections."
        )
    return httpx.AsyncClient(base_url=settings.AIRBYTE_API_URL, headers={"Authorization": f"Bearer {settings.AIRBYTE_API_KEY}"}, timeout=30.0)


async def list_source_definitions() -> list[dict]:
    """The real, live list of Airbyte's 300+ available source
    connectors -- read from Airbyte itself, never hardcoded here (a
    static list would drift the moment Airbyte adds or removes one)."""
    async with _client() as client:
        response = await client.post("/api/v1/source_definitions/list", json={"workspaceId": settings.AIRBYTE_WORKSPACE_ID})
        response.raise_for_status()
        return response.json().get("sourceDefinitions", [])


async def create_source(*, name: str, source_definition_id: str, connection_configuration: dict) -> dict:
    async with _client() as client:
        response = await client.post("/api/v1/sources/create", json={
            "workspaceId": settings.AIRBYTE_WORKSPACE_ID, "name": name,
            "sourceDefinitionId": source_definition_id, "connectionConfiguration": connection_configuration,
        })
        response.raise_for_status()
        return response.json()


async def get_source_catalog(source_id: str) -> dict:
    async with _client() as client:
        response = await client.post("/api/v1/sources/discover_schema", json={"sourceId": source_id})
        response.raise_for_status()
        return response.json()


async def create_connection(*, source_id: str, destination_id: str, sync_catalog: dict) -> dict:
    async with _client() as client:
        response = await client.post("/api/v1/connections/create", json={
            "sourceId": source_id, "destinationId": destination_id, "syncCatalog": sync_catalog, "status": "active",
        })
        response.raise_for_status()
        return response.json()


async def trigger_sync(airbyte_connection_id: str) -> dict:
    async with _client() as client:
        response = await client.post("/api/v1/connections/sync", json={"connectionId": airbyte_connection_id})
        response.raise_for_status()
        return response.json()


async def get_sync_status(job_id: str) -> dict:
    async with _client() as client:
        response = await client.post("/api/v1/jobs/get", json={"id": job_id})
        response.raise_for_status()
        return response.json()


async def list_connections(db: AsyncSession, organization_id: uuid.UUID) -> list[AirbyteConnection]:
    from sqlalchemy import select

    return list((await db.scalars(select(AirbyteConnection).where(AirbyteConnection.organization_id == organization_id))).all())


async def record_connection(db: AsyncSession, organization_id: uuid.UUID, *, name: str, airbyte_source_id: str, airbyte_connection_id: str, source_type: str, user_id: uuid.UUID | None) -> AirbyteConnection:
    row = AirbyteConnection(organization_id=organization_id, name=name, airbyte_source_id=airbyte_source_id, airbyte_connection_id=airbyte_connection_id, source_type=source_type, created_by=user_id)
    db.add(row)
    await db.flush()
    return row
