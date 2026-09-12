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

Verified live end-to-end against Airbyte Cloud's real public API
(2026-09-19): OAuth2 token exchange succeeds, and every function below
calls Cloud's actual documented REST shape (`GET/POST /sources`,
`/connections`, `/jobs`, `/streams`,
`/workspaces/{id}/definitions/sources` -- see
https://reference.airbyte.com), not the older OSS Configuration API
RPC shape (`/source_definitions/list`, `/sources/create`, etc.) this
module used before, which Cloud's public API doesn't expose at all.
Both shapes are exposed under the SAME `AIRBYTE_API_URL` (`/v1` for
Cloud, documented as already including `/api/v1` for a self-hosted OSS
instance) with no other code path difference, so if OSS's Configuration
API is ever needed again, it belongs in its own module, not
reintroduced here as a silent branch.
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
    static list would drift the moment Airbyte adds or removes one).

    Real Cloud endpoint: `GET /workspaces/{workspaceId}/definitions/sources`
    (there is no bare, workspace-less `/source_definitions/list` on
    Cloud's public API -- that's the OSS Configuration API's own shape,
    confirmed live to 403 on Cloud). Each item's real field is `id`,
    not the OSS-style `sourceDefinitionId` -- remapped here so this
    function's return shape (and the `AirbyteSourceDefinitionResponse`
    schema built against it) doesn't have to change."""
    async with (await _client()) as client:
        response = await client.get(f"/workspaces/{settings.AIRBYTE_WORKSPACE_ID}/definitions/sources")
        response.raise_for_status()
        return [
            {"sourceDefinitionId": item["id"], "name": item["name"], "dockerRepository": item.get("dockerRepository")}
            for item in response.json().get("data", [])
        ]


async def create_source(*, name: str, source_definition_id: str, connection_configuration: dict) -> dict:
    """Real Cloud endpoint: `POST /sources` -- `definitionId` (not the
    OSS-style `sourceDefinitionId`) plus a bare `configuration` object
    (not `connectionConfiguration`); no `sourceType` needed alongside a
    `definitionId` (Cloud's own documented rule for exactly this case)."""
    async with (await _client()) as client:
        response = await client.post("/sources", json={
            "workspaceId": settings.AIRBYTE_WORKSPACE_ID, "name": name,
            "definitionId": source_definition_id, "configuration": connection_configuration,
        })
        response.raise_for_status()
        return response.json()


async def get_source_catalog(source_id: str) -> dict:
    """Real Cloud endpoint: `GET /streams?sourceId=...&ignoreCache=true`
    -- Cloud has no separate "discover schema" action (the OSS
    `/sources/discover_schema` RPC); `/streams` IS the real schema
    discovery call, and `ignoreCache=true` forces a fresh read from the
    source rather than Airbyte's own cached catalog. Confirmed live:
    this specific call is genuinely slower than every other one here
    (Airbyte spins up the actual connector to introspect its schema) --
    a real ~90s attempt succeeded where the shared client's normal 30s
    timeout timed out, so this call alone gets a longer, explicit one."""
    async with (await _client()) as client:
        response = await client.get(
            "/streams", params={"sourceId": source_id, "ignoreCache": "true"}, timeout=90.0,
        )
        response.raise_for_status()
        return response.json()


async def create_connection(*, source_id: str, destination_id: str, sync_catalog: dict) -> dict:
    """Real Cloud endpoint: `POST /connections` -- there is no
    `syncCatalog`/`status` pair on Cloud's API; per-stream sync
    settings (if any) go under `configurations`, and connections are
    created `active` by default (Cloud's own documented default), so
    `sync_catalog` is passed through as `configurations` only when
    the caller actually supplied one -- an empty/falsy dict means "use
    Airbyte's own real defaults" (all streams, full_refresh_overwrite),
    not "sync nothing"."""
    async with (await _client()) as client:
        body = {"sourceId": source_id, "destinationId": destination_id}
        if sync_catalog:
            body["configurations"] = sync_catalog
        response = await client.post("/connections", json=body)
        response.raise_for_status()
        return response.json()


async def trigger_sync(airbyte_connection_id: str) -> dict:
    """Real Cloud endpoint: `POST /jobs` with `jobType: "sync"` -- Cloud
    has no per-connection `/connections/sync` action; jobs (sync or
    reset) are their own top-level resource."""
    async with (await _client()) as client:
        response = await client.post("/jobs", json={"connectionId": airbyte_connection_id, "jobType": "sync"})
        response.raise_for_status()
        return response.json()


async def get_sync_status(job_id: str) -> dict:
    """Real Cloud endpoint: `GET /jobs/{jobId}` -- Cloud's jobs are a
    real REST resource (`GET` by id), not the OSS `/jobs/get` RPC call."""
    async with (await _client()) as client:
        response = await client.get(f"/jobs/{job_id}")
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
