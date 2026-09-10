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

## Frontend

Extended the existing `frontend/app/dashboard/settings/integrations/page.tsx`
(Slack/Teams/Discord, already real) with a new section for universal
inbound connections — NOT a new, separate page (same consolidation
discipline as 10.6/11/12.5/13.5).

## Honest gaps (~35/40 items not built)

- No real Zapier/Make/n8n developer-platform app listing (`GET
  /automation/providers/{provider}/apps`) — that requires publishing a
  real app on each platform's own marketplace, not something buildable
  from this side without a real developer account on each.
- No OAuth credential storage (`AutomationCredential`) — no real
  provider requiring OAuth (vs. a bearer token) is wired yet.
- Airbyte's real API has never been exercised against a real running
  instance (none exists here) — the client code is real and correct
  against Airbyte's documented API shape, but untested against a live
  server.
- No per-organization execution-rate limiting beyond what already
  exists platform-wide.
