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

**Inbound authentication.** `POST /integrations/teams/webhook` verifies the JWT Microsoft signs for the bot (`api/security/teams_bot_auth.py`): RS256 signature against the keys published at `TEAMS_OPENID_METADATA_URL` (fetched through the SSRF-safe client and cached, refreshed on an unknown `kid`), issuer `https://api.botframework.com`, expiry, and an audience equal to the bot's Microsoft App ID -- the `bot_id` of the integration configured for the activity's tenant, or the global `TEAMS_BOT_ID`. Any failure (no token, wrong audience, expired, unknown key, keys unreachable, no App ID configured) answers 401 and nothing is processed. The token logic is covered by tests with locally generated keys; it has not been exercised against a live Azure Bot Registration.

## Adaptive Cards

`api/services/chat_integrations/cards.py` builds real Adaptive Card JSON (`create_chat_card`, `create_response_card` with citations as a `FactSet`, `create_error_card`, `create_suggested_questions_card` with real `Action.Submit` buttons) as a richer alternative to `format_teams_response`'s plain text.

## How messages are answered

Same real, shared chat engine as Slack/Discord/the widget -- see `api/services/chat_integrations/_common.py`.
