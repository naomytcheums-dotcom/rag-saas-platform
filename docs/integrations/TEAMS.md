# Microsoft Teams integration (Partie 9.4.2)

## Setup (incoming webhook -- simplest path)

1. In the target Teams channel: **⋯ → Connectors → Incoming Webhook**, create one, copy its URL.
2. Configure your organization:

```
POST /organizations/{org_id}/integrations/teams/configure
{ "webhook_url": "https://outlook.office.com/webhook/...", "agent_id": "..." }
```

`send_teams_response` posts real messages to that webhook -- no Azure Bot Registration required for this path.

## Setup (full Bot Framework bot -- richer, receives real inbound messages)

1. Register a bot in the Azure Bot Service, note its App ID.
2. Set the bot's messaging endpoint to `https://your-instance.example.com/integrations/teams/webhook`.
3. Configure: `POST /organizations/{org_id}/integrations/teams/configure` with `tenant_id`, `bot_id`, `bot_token`, `agent_id`.

⚠️ **Honest limitation**: the inbound `/integrations/teams/webhook` endpoint does not yet verify the real, live JWKS-backed Bot Framework bearer token (Microsoft's own JWKS endpoint changes over time and this environment has no live Azure Bot Registration to test against) -- see `api/services/chat_integrations/teams.py`'s own top docstring. The real message-processing/formatting/Adaptive-Card logic is fully implemented and tested; wiring a live JWKS check onto the inbound webhook is the one remaining piece for a production deployment.

## Adaptive Cards

`api/services/chat_integrations/cards.py` builds real Adaptive Card JSON (`create_chat_card`, `create_response_card` with citations as a `FactSet`, `create_error_card`, `create_suggested_questions_card` with real `Action.Submit` buttons) as a richer alternative to `format_teams_response`'s plain text.

## How messages are answered

Same real, shared chat engine as Slack/Discord/the widget -- see `api/services/chat_integrations/_common.py`.
