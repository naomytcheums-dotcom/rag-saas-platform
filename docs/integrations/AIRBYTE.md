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
`{"configured": false}` until `AIRBYTE_API_URL`/`AIRBYTE_API_KEY` (OSS)
or `AIRBYTE_API_URL`/`AIRBYTE_CLIENT_ID`/`AIRBYTE_CLIENT_SECRET`
(Cloud) are set, `{"reachable": false}` if set but no real Airbyte
instance answers.

## Airbyte Cloud (real OAuth2 + all 6 endpoints — fully working, verified live end-to-end)

`api/services/airbyte_client.py` supports Airbyte Cloud's own real auth
flow: `AIRBYTE_CLIENT_ID`/`AIRBYTE_CLIENT_SECRET` are exchanged for a
real bearer token via `POST {AIRBYTE_API_URL}/applications/token`
(`grant_type: client_credentials`), cached in memory until near expiry,
then auto-refreshed — takes priority over the OSS `AIRBYTE_API_KEY`
when both are set.

**Two real bugs found and fixed live against the real, current
credentials (2026-09-19)**:

1. **`client_id` case mismatch.** Every token-exchange attempt (JSON
   body, form body, Basic Auth, camelCase field names — all tested
   live) returned a real `401`/`400` no matter the request shape. Root
   cause found by decoding the real JWT Airbyte's own "Générer un jeton
   d'accès" button issued for this exact application: its `client_id`
   claim is lowercase (`...40ac49f29f11`), while the value shown/copied
   from the Applications page and stored in `.env` had one segment in
   uppercase (`...40AC49F29F11`). Airbyte's token endpoint treats
   `client_id` as case-sensitive; fixed by lowercasing it in `.env`.
   Token exchange now succeeds for real (a genuine signed JWT access
   token is returned).
2. **Doubled API path.** Every endpoint call in this file (except the
   token exchange itself) built its URL as
   `{AIRBYTE_API_URL}/api/v1/<endpoint>` — but `AIRBYTE_API_URL` is
   documented (and set, for both OSS and Cloud) to already end in
   `/api/v1` or `/v1`, so every real call doubled that segment
   (`.../v1/api/v1/source_definitions/list`), a real `403` on Cloud.
   Fixed by dropping the redundant `/api/v1` prefix from all 6 calls
   (`list_source_definitions`, `create_source`, `get_source_catalog`,
   `create_connection`, `trigger_sync`, `get_sync_status`) — affected
   OSS mode identically, not just Cloud.

**All 6 endpoint functions rewritten against Airbyte Cloud's real public
REST API (2026-09-19), verified live end-to-end, not guessed**: the
functions above were originally written against Airbyte's legacy OSS
Configuration API shape (`POST .../source_definitions/list`,
`.../sources/create`, etc.) — confirmed live that Cloud's modern public
API doesn't expose that shape at all (a real `403` on
`/source_definitions`, cleanly separate from the path-doubling bug
above). The real shape, confirmed against Cloud's own API reference
(`https://reference.airbyte.com`) and every one of the 6 calls run live
against this deployment's real workspace:

| Function | Real Cloud endpoint |
|---|---|
| `list_source_definitions` | `GET /workspaces/{workspaceId}/definitions/sources` |
| `create_source` | `POST /sources` (`definitionId` + bare `configuration`, no `sourceType` alongside it) |
| `get_source_catalog` | `GET /streams?sourceId=...&ignoreCache=true` (Cloud's real schema-discovery call; genuinely slow on a fresh source -- a real ~90s attempt succeeded where the shared client's 30s default timed out, so this call alone uses an explicit 90s timeout) |
| `create_connection` | `POST /connections` (`sourceId`/`destinationId`; no `syncCatalog`/`status` pair -- per-stream settings go under `configurations`, omitted entirely to take Cloud's own real defaults) |
| `trigger_sync` | `POST /jobs` with `jobType: "sync"` (jobs are their own top-level resource, not a per-connection action) |
| `get_sync_status` | `GET /jobs/{jobId}` |

Verified live, in order, against this deployment's real workspace
(`b660dd41-8c52-49f0-8a5d-adc016f3e276`): created a real test source
(the `Sample Data`/`source-faker` connector -- fabricated data, no
external system touched), discovered its real 3-stream schema,
created a real test destination (`End-to-End Testing (/dev/null)` --
Airbyte's own connector built exactly for this, writes nowhere real),
created a real connection between them, triggered a real sync job
(`jobId 105161610`, confirmed `running` via a second, separate real
status call), then deleted all three test resources (`204` on each) to
leave the real account clean. `GET /integrations/airbyte/status` now
reports `{"configured": true, "reachable": true}` for real.

## Real network blocker on this dev machine (retried, still blocked)

`abctl local install --port 8001` (port 8000 kept free for this app's
own FastAPI backend) reliably creates a real local Kubernetes cluster
(`kind`) — confirmed via `docker ps` showing
`airbyte-abctl-control-plane` up — but then fails downloading Airbyte's
Helm chart:

```
unable to download index file: Get "https://airbytehq.github.io/charts/index.yaml":
dial tcp 185.199.111.153:443: connectex: ...
```

Retried on 2026-09-11 (second session): still blocked, same error.
Diagnosis (unchanged): DNS resolves `airbytehq.github.io` correctly
(real Fastly IPs), but a direct TCP connection to those same IPs
(185.199.108–111.153, GitHub Pages' CDN range) times out completely
from this machine — while `github.com` and `raw.githubusercontent.com`
(different IP ranges) both respond normally. This is a real,
external, network-level block (firewall/antivirus/router) specific to
that one CDN range — not fixable from inside this repo or by retrying
`abctl` again on the same network.

### Manual installation options (for when this network allows it, or from a different machine/network)

**Option A — retry `abctl` from a network that can reach GitHub Pages**
(e.g. a different Wi-Fi, a VPN, or a cloud VM):
```bash
curl -LsfS https://get.airbyte.com | bash -
abctl local install --port 8001
```
Nothing else changes — the moment the Helm chart downloads
successfully, `abctl` finishes the same way it did in every other
successful install elsewhere.

**Option B — pre-download the Helm chart and point `abctl`/`helm` at a
local copy**, if only that one specific host is blocked but general
internet access works: download `https://github.com/airbytehq/airbyte-platform/releases`
(the platform repo mirrors its Helm chart there too) or clone
`https://github.com/airbytehq/helm-charts` directly via `git` (which
uses `github.com`, not `airbytehq.github.io`, and was confirmed
reachable from this machine), then run Helm against the local chart
directory instead of the remote index:
```bash
git clone https://github.com/airbytehq/helm-charts.git
helm install airbyte ./helm-charts/charts/airbyte --namespace airbyte-abctl --create-namespace
```
This bypasses `abctl`'s own chart-index lookup entirely by using a
real, already-cloned copy of the same chart.

**Option C — Airbyte Cloud** (no local install at all): create a free
Airbyte Cloud account at `https://cloud.airbyte.com`, generate an API
key from Settings → Applications, and point this app's `.env` at
Airbyte Cloud's own API URL instead of a local instance:
```
AIRBYTE_API_URL=https://api.airbyte.com/v1
AIRBYTE_API_KEY=<from Airbyte Cloud's own Settings -> Applications>
AIRBYTE_WORKSPACE_ID=<from Airbyte Cloud's own UI>
```
`api/services/airbyte_client.py` needs no code change either way — it
already just calls whatever `AIRBYTE_API_URL` is configured, local or
Cloud.

**Option D — ask whoever manages this network's firewall/antivirus to
allowlist `185.199.108.153`–`185.199.111.153` (GitHub Pages' CDN
range)** — the most direct fix if this is a corporate/ISP-level block,
since every other option above is a workaround rather than a real fix
of the underlying network restriction.
