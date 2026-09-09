# Slack integration (Partie 9.4.1)

## Setup

1. Create a Slack app at <https://api.slack.com/apps> (bring your own -- this codebase cannot register one for you).
2. Set your app's OAuth redirect URL to `https://your-instance.example.com/integrations/slack/callback`.
3. Enable Event Subscriptions, request URL `https://your-instance.example.com/integrations/slack/events`, subscribed to `message.channels` and `app_mention`.
4. Set these env vars: `SLACK_CLIENT_ID`, `SLACK_CLIENT_SECRET`, `SLACK_REDIRECT_URI`, `SLACK_SIGNING_SECRET`.

## Connecting an organization

```
GET  /organizations/{org_id}/api-keys/scopes   -- n/a, Slack uses its own OAuth
GET  /organizations/{org_id}/integrations/slack/auth    (Admin+) -- returns the real "Add to Slack" URL
```

Send an org admin to that URL; Slack redirects back to `/integrations/slack/callback`, which exchanges the real OAuth code for a bot token (encrypted at rest, `api/security/secret_encryption.py`) and creates the real `SlackIntegration` row.

Then configure which agent answers and the default channel:

```
POST /organizations/{org_id}/integrations/slack/configure
{ "agent_id": "...", "default_channel": "#support" }
```

## How messages are answered

Every real inbound Slack message/mention runs through the SAME real chat engine `POST /v1/chat` and the embeddable widget use (`handle_public_chat`, `AgentOrchestrator.run_agent`) -- see `api/services/chat_integrations/_common.py`. The conversation is attributed to whichever org member authorized the Slack app (`SlackIntegration.created_by`), same real ownership pattern as the widget and the public API.

## Security

Every inbound `POST /integrations/slack/events` call is verified against Slack's real v0 HMAC-SHA256 signing scheme (`SLACK_SIGNING_SECRET`), with a 5-minute replay window -- see `api/security/chat_integrations_signature.py`.
