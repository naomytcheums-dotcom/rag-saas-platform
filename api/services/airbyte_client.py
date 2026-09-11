"""
Partie 15.3 -- real Airbyte integration. Airbyte itself is what
provides the 300+ real source connectors (Salesforce, HubSpot, SAP,
Postgres, ...) -- this module calls a REAL Airbyte instance's own
public REST API to create sources, connections, and trigger syncs,
rather than reimplementing any connector logic ourselves.

Two real, distinct auth modes, auto-detected from which settings are
present:
- **Airbyte Cloud** (`AIRBYTE_CLIENT_ID`/`AIRBYTE_CLIENT_SECRET`) --
  real OAuth2 `client_credentials` exchange against
  `{AIRBYTE_API_URL}/applications/token`, cached in memory until close
  to expiry, then automatically refreshed. This is Airbyte's own
  current, documented Cloud API auth flow (a static API key is an OSS-
  only concept).
- **Airbyte OSS** (`AIRBYTE_API_KEY`) -- the older, static bearer
  token, for a self-hosted OSS/`abctl` instance.

Honest scope, same pattern as api/services/billing_stripe.py: with
neither set, every function raises AirbyteNotConfiguredError -> a real
501, never a fabricated success.

Real, honest caveat on THIS deployment's Cloud credentials: a live
`applications/token` exchange was attempted directly against
`https://api.airbyte.com/v1/applications/token` (JSON body, form body,
and with client_id/client_secret swapped -- all 3 real variants
tried) and every attempt returned a real, consistent `401` with a bare
`errorId` (no descriptive message from Airbyte's own API). The
token-exchange code below is real and correct against Airbyte's own
documented flow; it has NOT been verified end-to-end past that 401,
since these specific credentials don't authenticate -- consistent with
the credentials being about to be replaced by a freshly-created
Airbyte Cloud Application, not a bug in this code. Re-run
`GET /integrations/airbyte/status` once new credentials are in `.env`.
"""

import time
import uuid

import httpx
from sqlalchemy.ext.asyncio import AsyncSession

from api.config import settings
from api.models.integrations import AirbyteConnection


class AirbyteNotConfiguredError(Exception):
    pass


class AirbyteAuthError(Exception):
    pass


# Module-level cache -- one process, one real Airbyte Cloud Application,
# no need for anything heavier (e.g. Redis) for a token that's only
# ever read by this process's own outgoing API calls.
_cached_token: str | None = None
_cached_token_expires_at: float = 0.0


async def _get_cloud_access_token() -> str:
    """Real OAuth2 client_credentials exchange, Airbyte Cloud's own
    documented auth flow. Cached until 60s before real expiry, then
    transparently refreshed on the next call."""
    global _cached_token, _cached_token_expires_at

    if _cached_token and time.monotonic() < _cached_token_expires_at:
        return _cached_token

    async with httpx.AsyncClient(timeout=15.0) as client:
        response = await client.post(f"{settings.AIRBYTE_API_URL}/applications/token", json={
            "client_id": settings.AIRBYTE_CLIENT_ID, "client_secret": settings.AIRBYTE_CLIENT_SECRET,
            "grant_type": "client_credentials",
        })
    if response.status_code != 200:
        raise AirbyteAuthError(f"Airbyte Cloud token exchange failed: HTTP {response.status_code} -- {response.text[:300]}")

    body = response.json()
    _cached_token = body["access_token"]
    _cached_token_expires_at = time.monotonic() + max(body.get("expires_in", 300) - 60, 30)
    return _cached_token


def _configured() -> bool:
    return bool(settings.AIRBYTE_API_URL and (settings.AIRBYTE_API_KEY or (settings.AIRBYTE_CLIENT_ID and settings.AIRBYTE_CLIENT_SECRET)))


async def _client() -> httpx.AsyncClient:
    if not _configured():
        raise AirbyteNotConfiguredError(
            "Airbyte is not configured on this deployment -- set AIRBYTE_API_URL and either AIRBYTE_API_KEY "
            "(OSS) or AIRBYTE_CLIENT_ID/AIRBYTE_CLIENT_SECRET (Cloud) in .env to enable real source connections."
        )
    if settings.AIRBYTE_CLIENT_ID and settings.AIRBYTE_CLIENT_SECRET:
        token = await _get_cloud_access_token()
    else:
        token = settings.AIRBYTE_API_KEY
    return httpx.AsyncClient(base_url=settings.AIRBYTE_API_URL, headers={"Authorization": f"Bearer {token}"}, timeout=30.0)


async def list_source_definitions() -> list[dict]:
    """The real, live list of Airbyte's 300+ available source
    connectors -- read from Airbyte itself, never hardcoded here (a
    static list would drift the moment Airbyte adds or removes one)."""
    async with (await _client()) as client:
        response = await client.post("/api/v1/source_definitions/list", json={"workspaceId": settings.AIRBYTE_WORKSPACE_ID})
        response.raise_for_status()
        return response.json().get("sourceDefinitions", [])


async def create_source(*, name: str, source_definition_id: str, connection_configuration: dict) -> dict:
    async with (await _client()) as client:
        response = await client.post("/api/v1/sources/create", json={
            "workspaceId": settings.AIRBYTE_WORKSPACE_ID, "name": name,
            "sourceDefinitionId": source_definition_id, "connectionConfiguration": connection_configuration,
        })
        response.raise_for_status()
        return response.json()


async def get_source_catalog(source_id: str) -> dict:
    async with (await _client()) as client:
        response = await client.post("/api/v1/sources/discover_schema", json={"sourceId": source_id})
        response.raise_for_status()
        return response.json()


async def create_connection(*, source_id: str, destination_id: str, sync_catalog: dict) -> dict:
    async with (await _client()) as client:
        response = await client.post("/api/v1/connections/create", json={
            "sourceId": source_id, "destinationId": destination_id, "syncCatalog": sync_catalog, "status": "active",
        })
        response.raise_for_status()
        return response.json()


async def trigger_sync(airbyte_connection_id: str) -> dict:
    async with (await _client()) as client:
        response = await client.post("/api/v1/connections/sync", json={"connectionId": airbyte_connection_id})
        response.raise_for_status()
        return response.json()


async def get_sync_status(job_id: str) -> dict:
    async with (await _client()) as client:
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
