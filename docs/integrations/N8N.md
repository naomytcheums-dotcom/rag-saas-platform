# n8n (local, via Docker Compose)

## Start

```bash
docker compose -f docker-compose.observability.yml up -d n8n n8n-postgres
```

Real Postgres persistence (`n8n-postgres`, its own credentials in
`docker-compose.observability.yml` — not the app's own database).
n8n UI: http://localhost:5678 — first launch prompts you to create an
owner account (real n8n behavior, not something this app configures).

## Connect n8n to this app

- **n8n → this app (real, already built)**: use n8n's own "HTTP Request"
  node against any of this app's real endpoints, authenticated with a
  real API key (`/dashboard/settings/api-keys`) or an organization's
  member account.
- **this app → n8n (real, already built)**: create a real inbound
  connection (`POST /organizations/{org_id}/integrations/connections`,
  `provider: "n8n"`, Partie 15.1/15.2) and give n8n the resulting
  `POST /integrations/inbound/{connection_id}` URL + bearer token as an
  n8n "Webhook" trigger's target, OR — the other direction — point an
  n8n workflow's own Webhook node's URL at this app's real outbound
  webhook system (`Webhook`/`WebhookDelivery`, Partie 9.2.7,
  `/organizations/{org_id}/webhooks`) to have n8n react to real
  platform events.

## Status check

`GET /integrations/n8n/status` — real reachability check against
`N8N_URL` (`.env`: `N8N_URL=http://localhost:5678`). Honestly reports
`{"configured": false, "reachable": false}` until `N8N_URL` is set and
`{"reachable": false}` if set but n8n isn't actually up.
