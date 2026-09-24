# Make (Integromat) App — RAG SaaS Platform

Official Make app for RAG SaaS Platform.

## Status

**This app is in development.** Make requires apps to be submitted to
their official marketplace (via their partner program) before they can
be installed by end users. Until then, users can connect via Make's
built-in **HTTP → Make a request** module (see
[../../docs/integrations/MAKE.md](../../docs/integrations/MAKE.md)).

## Structure

- `app.yaml` — Make app manifest (base URL, auth type, modules)
- `connections/` — OAuth/API-key connection definitions
- `modules/` — Actions exposed to Make scenarios
- `webhooks/` — Inbound webhook definitions
- `functions/` — Custom IML functions (if any)

## Modules

| Module | Type | Description |
|--------|------|-------------|
| `ingestDocument` | Action | Send text/data to the RAG pipeline |
| `createAgent` | Action | Create a new Agent in an organization |
| `createConversation` | Action | Create a new Conversation |
| `sendNotification` | Action | Send an in-app + email notification |
| `triggerWorkflow` | Action | Trigger a Workflow run |
| `watchNewDocument` | Trigger | Fires when a new document is ingested |
| `watchNewConversation` | Trigger | Fires when a new conversation starts |

## Installation (for developers)

1. Register as a Make partner: https://www.make.com/en/partner
2. Create a new app in the Make Developer Hub
3. Upload the manifest from `app.yaml`
4. Configure the OAuth connection (or API-key connection)
5. Submit for review

## Authentication

Make app uses a **Bearer Token** connection type:

- **Base URL**: user-provided (their RAG SaaS instance)
- **Connection ID**: user-provided
- **Token**: user-provided (generated in the dashboard)

Same auth shape as n8n (see
[../../docs/integrations/N8N.md](../../docs/integrations/N8N.md)).

## Local testing

Use Make's own `make-cli`:
```bash
npm install -g @makehq/cli
make-cli app:validate
make-cli app:test
OAuth connection
Modules implementation
Webhook triggers
Partner program submission
Manifest structure
Documentation (via HTTP module)
Manifest structure (app.yaml)
Marketplace publication
