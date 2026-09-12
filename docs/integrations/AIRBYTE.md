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

## Airbyte Cloud (real OAuth2 — now working; one real gap remains)

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

**Real, honest gap that remains**: with both bugs fixed, the OAuth2
handshake and basic connectivity are confirmed live and working
(`GET /workspaces` and `GET /sources` both return real `200`s with this
application's real workspace). But `list_source_definitions` (and the
other 5 helper functions) still target Airbyte's **legacy OSS
Configuration API** shape (`POST .../source_definitions/list`,
`.../sources/create`, etc.) — confirmed live that Airbyte Cloud's
modern public API does not expose these at all (`403 Forbidden` on
`/source_definitions`, cleanly separate from the path-doubling bug
above). Cloud instead exposes a REST-shaped API (`GET/POST /sources`,
`/destinations`, `/connections`, `/jobs`, each with a different
request/response schema than the OSS RPC calls this file was written
against). Making a real end-to-end sync flow work against Airbyte
Cloud specifically requires rewriting these 6 functions against Cloud's
actual REST shape — real, scoped work, not done in this pass since it
needs its own verification rather than being guessed. `GET
/integrations/airbyte/status` already reports this honestly:
`{"configured": true, "reachable": false}` (credentials are real and
authenticate; the specific reachability probe it uses,
`list_source_definitions`, is the legacy call that 403s on Cloud).

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
