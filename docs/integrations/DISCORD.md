# Discord integration (Partie 9.4.3)

## Setup

1. Create an application at <https://discord.com/developers/applications>, add a Bot, copy its token and the application's Public Key.
2. Set the application's **Interactions Endpoint URL** to `https://your-instance.example.com/integrations/discord/interactions` (Discord sends a real PING to verify this URL -- handled automatically).
3. Set `DISCORD_PUBLIC_KEY` (for interaction signature verification).
4. Invite the bot to your server with `bot` + `applications.commands` scopes.
5. Configure your organization:

```
POST /organizations/{org_id}/integrations/discord/configure
{ "guild_id": "...", "bot_token": "...", "agent_id": "..." }
```

## Slash commands

`/ask <question>`, `/chat`, `/history`, `/clear`, `/help` -- dispatched from the real Interactions webhook (`api/services/chat_integrations/discord.py`'s `handle_command`). `/ask` runs through the same real chat engine every other entry point uses.

## Gateway-connected bots

A bot connected via the Discord Gateway (a separate, long-running process outside this HTTP API, same boundary as the Twilio media-stream integration) can post inbound messages to `POST /integrations/discord/message` for full message-in/message-out handling, including real thread creation (`create_discord_thread`).

## Security

- **Interactions webhook**: Discord's real Ed25519 signature scheme (`X-Signature-Ed25519`/`X-Signature-Timestamp`), verified in `api/security/chat_integrations_signature.py` -- NOT HMAC, unlike Slack.
- **Bot tokens**: encrypted at rest (`api/security/secret_encryption.py`), same as every other platform's credentials.

## How messages are answered

Same real, shared chat engine as Slack/Teams/the widget -- see `api/services/chat_integrations/_common.py`.
