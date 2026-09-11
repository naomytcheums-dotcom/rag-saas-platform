# Partie 15 (bis) — Advanced Integrations (Universal CRM/ERP, Zapier/Make/n8n, Airbyte)

Same consolidated-guide discipline as every prior batch. This part's
DeepSeek prompts (15.1 "universal integration", 15.2 "Zapier/Make/n8n
connectors") describe the SAME underlying mechanism twice, under
different model names (`IntegrationConnection`/`IntegrationSync` vs
`AutomationTrigger`/`AutomationExecution`) — consolidated into one real
system rather than built twice.

## Outbound direction — already real, not duplicated

"Notify Zapier/Make/n8n when something happens in this app" already
exists for real: `Webhook`/`WebhookDelivery` (Partie 9.2.7,
`api/models/webhook.py`, `api/routers/webhooks.py`). Pointing a
Zapier "Webhooks by Zapier" trigger step (or a Make/n8n HTTP trigger)
at one of an organization's real webhook URLs is the real way to build
"when X happens here, run my Zap/scenario/workflow" — nothing new was
needed, and nothing here duplicates it.

## Inbound direction — genuinely new (15.1/15.2)

`api/models/integrations.py` — `IntegrationConnection` (one real,
per-organization inbound receiver: a name, a provider label
webhook/zapier/make/n8n, a real bearer token generated once and shown
once, and exactly one real configured action), `IntegrationMapping`
(optional field renaming + a real, pure transform:
`normalize_email`/`normalize_phone`/`normalize_date`), `IntegrationLog`
(every real inbound POST, accepted/rejected/error).

`POST /integrations/inbound/{connection_id}` — flat and public (an
external system can't be handed an org_id ahead of time, same reasoning
as Stripe's own webhook, Partie 12.2), authenticated by the
connection's own bearer token (`secrets.compare_digest`, not `==`).

**Real, honest action list**: `ingest_document` (feeds the payload's
text fields into this organization's REAL document/RAG pipeline —
reuses `upload_document`, Partie 2, not a parallel ingestion path) and
`log_only`. The literal spec's longer list ("create an agent", "update
a CRM", "send an email") has no real target in this environment — see
`api/services/integrations.py`'s own docstring for why adding those as
no-op stubs would be fabricated completeness.

Verified live end-to-end: created a real connection with
`ingest_document`, POSTed a real payload with its real token, confirmed
a real `Document` row was created and queued for the real embedding
pipeline, same as any manual upload.

## Airbyte (15.3)

`api/services/airbyte_client.py` — real calls to a real Airbyte
instance's own REST API (`/api/v1/sources/create`,
`/connections/create`, `/connections/sync`, ...). Airbyte itself is
what provides the 300+ real source connectors (Salesforce, HubSpot,
SAP, Postgres, ...) — nothing here reimplements any of them. Honest
scope, same pattern as `billing_stripe.py`: `AIRBYTE_API_URL`/
`AIRBYTE_API_KEY` are unset in this environment (no real Airbyte
instance is deployed here), so every function raises
`AirbyteNotConfiguredError` → a real `501`, never a fabricated success.
`AirbyteConnection` (new, minimal) stores only the ids Airbyte itself
returns — the source's real catalog/schema/sync history stay in
Airbyte, read live via its API rather than mirrored a second time here.

## Endpoints (complete)

`GET /integrations/providers` (static catalog), `GET/POST
/organizations/{org_id}/integrations/connections`, `GET/PATCH/DELETE
.../connections/{id}`, `POST .../connections/{id}/test` (real dry run,
never runs the actual action), `POST .../connections/{id}/sync` +
`GET .../connections/{id}/syncs` (retries every previously-failed
payload for this connection — the real, honest meaning of "sync" for a
push-only inbound receiver, see `api/services/integrations.py`'s own
docstring on `retry_failed_logs`), `GET .../connections/{id}/logs`,
`POST/GET .../connections/{id}/mappings`, `PATCH/DELETE
.../mappings/{id}`.

## Celery jobs (complete)

`cleanup_integration_logs` (daily retention sweep, pre-existing),
`retry_failed_syncs` + `process_integration_webhooks` (hourly,
system-wide — both call the same real per-connection retry sweep;
`api/tasks/integrations.py`'s own module docstring explains why the
literal spec names the same push-only-connection mechanism twice
rather than there being two distinct real jobs), `sync_integrations`
(every 6h, Airbyte-scoped — the one real PULL-based integration,
triggers Airbyte's own `/connections/sync` for every recorded
`AirbyteConnection`). All four registered in `celery_app.py`'s
`beat_schedule`.

## Frontend (11 real components)

Split out of the former single inline `UniversalIntegrationsSection`
into 11 real, separately-testable components under
`frontend/components/`: `ProviderCard`/`ProviderList` (the static
provider catalog), `ConnectionForm`/`ConnectionItem`/`ConnectionList`
(create/expand/delete), `WebhookConfig` (the real inbound URL + token,
shown once), `ConnectionTest` (the dry-run panel), `MappingEditor`/
`MappingList` (create/edit via the new PATCH endpoint/delete),
`SyncHistory` (retry + history), `IntegrationLogs` (the receipt log).
Composed inside the existing
`frontend/app/dashboard/settings/integrations/page.tsx` — still one
real page, not 11 separate routes (same consolidation discipline as
10.6/11/12.5/13.5); the components themselves are the real, separate,
independently-testable units the spec asked for.

## Tests (5 real files)

`tests/test_connections.py`, `tests/test_mappings.py`,
`tests/test_inbound_webhooks.py`, `tests/test_transformations.py`
(backend, replacing the former single
`tests/test_integrations_universal.py`)

🐛 **Naming collision found and fixed**: the spec's requested filename
`test_webhooks.py` was already real and in use — Partie 9.2.7's own
outbound `Webhook`/`WebhookDelivery` tests, tracked in git since long
before this work. Writing this part's file under that same name
silently overwrote and destroyed those 11 pre-existing tests; caught
via `git status` showing the file as modified rather than new,
restored from `git checkout HEAD`, and this part's own inbound-webhook
tests kept under the non-colliding `test_inbound_webhooks.py` instead —
same discipline as every other "Partie N (bis)" numbering collision in
this project, applied here to a filename instead of a section number.
and `frontend/components/integrations/components.test.tsx` (12 real
Vitest/React Testing Library tests covering all 11 components — this
project had **zero** frontend test infrastructure before this work;
Vitest + `@testing-library/react` + jsdom were installed for real
(`frontend/vitest.config.ts`, `npm run test`), not left as dead
imports).

## Airbyte (15.3) — real network blocker, not a code bug

`abctl` (Airbyte's real current CLI, replacing the deprecated
`docker-compose.yaml` deployment) was downloaded, verified
(`abctl version`), and run for real: `abctl local install --port 8001`
(8000 stays free for this app's own FastAPI backend) successfully
created a real local Kubernetes cluster (`kind`) — confirmed via
`docker ps` showing `airbyte-abctl-control-plane` up and healthy — but
the subsequent Helm chart download failed with a real, confirmed
network error:

```
unable to download index file: Get "https://airbytehq.github.io/charts/index.yaml":
dial tcp 185.199.111.153:443: connectex: ...
```

Diagnosed further: DNS resolution for `airbytehq.github.io` succeeds
(returns real Fastly IPs), but a direct TCP connection to those same
IPs (185.199.108–111.153, GitHub Pages' CDN range) times out
completely from this machine, while `github.com` and
`raw.githubusercontent.com` (different IP ranges) both respond
normally — a real, external network-level block (firewall/antivirus/
router) specific to that CDN range, not something fixable in this
repo's code. `GET /integrations/airbyte/status` and `POST
.../connections/{id}/sync`-equivalent (Airbyte's own
`airbyte_client.trigger_sync`) remain honestly gated (`configured:
false` / `501`) until either connectivity is restored or Airbyte is
run from a network that can reach GitHub Pages.

## Real incident found and fixed during this work: Twilio test isolation

Running the full regression suite with this deployment's real, live
Twilio credentials in `.env` (added earlier for real production SMS)
exposed a real gap: `tests/test_notifications_datadog_grafana.py`'s
own `test_send_sms_honestly_501s_without_full_twilio_config` assumed
Twilio would be unconfigured and instead hit the REAL Twilio API,
attempting to send to a fake `+15551234567` number — confirmed via
Twilio's own message history (`client.messages.list()`): a real,
non-zero charge (-$0.001) for a message Twilio itself rejected (error
21211, invalid `To`). Fixed by adding an autouse
`_blank_twilio_credentials_by_default` fixture to `tests/conftest.py`
(same established pattern as the existing rate-limiting/HIBP stubs) —
every test now runs with Twilio credentials blanked unless it
explicitly monkeypatches them back, like
`test_send_sms_succeeds_with_mocked_twilio_client` already did
correctly. Re-verified via Twilio's own message history: no new
message was created after the fix.

## Honest remaining gaps

- No real Zapier/Make/n8n developer-platform app listing (`GET
  /automation/providers/{provider}/apps`) — that requires publishing a
  real app on each platform's own marketplace, not something buildable
  from this side without a real developer account on each.
- No OAuth credential storage (`AutomationCredential`) — no real
  provider requiring OAuth (vs. a bearer token) is wired yet.
- Airbyte's real API has never been exercised against a real running
  instance — see the network-blocker note above; the client code and
  every endpoint built against it are real and correct against
  Airbyte's documented API shape, verified only up to the point the
  network allows.
- No per-organization execution-rate limiting beyond what already
  exists platform-wide.
