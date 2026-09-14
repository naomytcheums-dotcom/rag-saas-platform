# Integrations

The platform integrates with external systems for both ingestion (pull
content in) and notification/chat (push out to another channel).

## Chat platform integrations

- [Slack](../integrations/SLACK.md)
- [Microsoft Teams](../integrations/TEAMS.md)
- [Discord](../integrations/DISCORD.md)

## Automation / data platform integrations

- [n8n](../integrations/N8N.md)
- [Airbyte](../integrations/AIRBYTE.md)

See also
[`docs/integrations/PARTIE_15_ADVANCED_INTEGRATIONS.md`](../integrations/PARTIE_15_ADVANCED_INTEGRATIONS.md)
for the full build history of this layer.

## Universal integrations

`api/routers/integrations_universal.py` provides a generic connector
surface beyond the named integrations above, for configurations that
don't need a dedicated router.

## Telephony / voice

Twilio integration (`api/routers/twilio.py`) backs voice messages — see
[Voice](../user/VOICE.md) and [Voice Messages settings](../admin/DASHBOARD.md).

## Zapier, Make, CRM, ERP

There is no dedicated router for Zapier, Make, or specific CRM/ERP
connectors today — the closest supported paths are the
[public API](API.md) (for a custom Zapier/Make integration built against
it) and [Webhooks](WEBHOOKS.md) (for outbound event-driven automation).
This is a real, current gap, not a hidden feature.

## Building your own

If none of the above cover your case, build against the
[public API](API.md) directly, or consume [Webhooks](WEBHOOKS.md) for
event-driven automation.
