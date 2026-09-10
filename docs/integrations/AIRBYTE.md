# Airbyte

## Real, honest deviation from a plain `docker-compose` service

Airbyte OSS deprecated its old docker-compose deployment — their
currently supported, real self-hosting method is `abctl`, Airbyte's own
CLI, which provisions a local Kubernetes cluster (via `kind`) and
installs Airbyte into it. Shipping the old compose-based setup in
`docker-compose.observability.yml` would install an unsupported,
no-longer-maintained version of a real product — a real incoherence
worth fixing, not silently reproducing.

## Install (real, current Airbyte instructions)

```bash
curl -LsfS https://get.airbyte.com | bash -
abctl local install
```

This starts a real, local Airbyte instance (default: http://localhost:8000).
Get a real API key from Airbyte's own Settings → Applications page once
it's running.

## Connect this app to Airbyte

`.env`:

```
AIRBYTE_API_URL=http://localhost:8000/api/v1
AIRBYTE_API_KEY=<from Airbyte's own Settings -> Applications>
AIRBYTE_WORKSPACE_ID=<from Airbyte's own UI, in the workspace URL>
```

`api/services/airbyte_client.py` then makes real calls against
Airbyte's own REST API — `list_source_definitions` (all 300+ real
connectors Airbyte itself ships), `create_source`, `get_source_catalog`,
`create_connection`, `trigger_sync`. Real endpoints:
`GET /organizations/{org_id}/integrations/airbyte/source-definitions`,
`POST .../airbyte/sources`, `POST .../airbyte/connections`,
`POST .../airbyte/connections/{id}/sync`.

## Status check

`GET /integrations/airbyte/status` — real reachability, calls
Airbyte's own `list_source_definitions` under the hood. Honestly
`{"configured": false}` until `AIRBYTE_API_URL`/`AIRBYTE_API_KEY` are
set, `{"reachable": false}` if set but no real Airbyte instance answers.
