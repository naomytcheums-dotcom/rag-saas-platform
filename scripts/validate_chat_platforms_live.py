#!/usr/bin/env python
"""Real validation of 9.4.1 Slack, 9.4.2 Microsoft Teams and 9.4.3 Discord: the OUTBOUND half of each integration, with the product's own senders.

    RUN_LIVE_VENDOR_VALIDATION=1 \
      SLACK_BOT_TOKEN=xoxb-... [LIVE_SLACK_CHANNEL=C0123456789] \
      DISCORD_BOT_TOKEN=... [LIVE_DISCORD_CHANNEL_ID=123456789012345678] \
      TEAMS_BOT_ID=<Microsoft App ID> TEAMS_APP_PASSWORD=<client secret> \
      python scripts/validate_chat_platforms_live.py

Without a channel variable the check is read-only (Slack `auth.test`, Discord `GET /users/@me`, Teams client-credentials token: each proves the token/secret is
accepted by the platform). With LIVE_SLACK_CHANNEL / LIVE_DISCORD_CHANNEL_ID ONE message "RAG platform validation" is posted there with the product's sender.

NOT covered here, and impossible from a script: the INBOUND half (Slack Events API and Discord Interactions delivered to a public HTTPS URL, Bot Framework
activities signed by Microsoft). That needs the apps registered with the platforms and the API reachable from the internet; the signature/JWT verification and
the reply logic are covered by tests/contracts/test_chat_integrations_contract.py against faithful local fakes.
"""
import asyncio
import os
import sys
from types import SimpleNamespace

import httpx

sys.path.insert(0, os.path.dirname(__file__))
import _live_vendor as live  # noqa: E402


async def main() -> int:
    live.require_opt_in("Slack, Discord, Microsoft Bot Framework", "free; at most one message per platform and only if a channel is given")
    crypto = live.product("api.security.secret_encryption")
    slack = live.product("api.services.chat_integrations.slack")
    discord = live.product("api.services.chat_integrations.discord")
    teams = live.product("api.services.chat_integrations.teams")
    report = live.Report("chat_platforms")

    if live.have("SLACK_BOT_TOKEN"):
        token = os.environ["SLACK_BOT_TOKEN"]

        async def identity():
            async with httpx.AsyncClient(timeout=15) as http:
                body = (await http.post("https://slack.com/api/auth.test", headers={"Authorization": f"Bearer {token}"})).json()
            assert body.get("ok"), body.get("error")
            return {"team": body.get("team"), "bot_user": body.get("user")}

        await report.check("slack:token", identity)
        if os.environ.get("LIVE_SLACK_CHANNEL"):
            integration = SimpleNamespace(bot_token=crypto.encrypt_secret(token))

            async def post():
                result = await slack.send_slack_response(integration, os.environ["LIVE_SLACK_CHANNEL"], "RAG platform validation")
                return {"ts": result.get("ts")}

            await report.check("slack:post", post)
    else:
        report.skipped("slack", "SLACK_BOT_TOKEN is not in the process environment")

    if live.have("DISCORD_BOT_TOKEN"):
        token = os.environ["DISCORD_BOT_TOKEN"]

        async def identity_discord():
            async with httpx.AsyncClient(timeout=15) as http:
                response = await http.get("https://discord.com/api/v10/users/@me", headers={"Authorization": f"Bot {token}"})
            assert response.status_code == 200, f"HTTP {response.status_code}"
            return {"bot": response.json().get("username")}

        await report.check("discord:token", identity_discord)
        if os.environ.get("LIVE_DISCORD_CHANNEL_ID"):
            integration = SimpleNamespace(bot_token=crypto.encrypt_secret(token))

            async def post_discord():
                result = await discord.send_discord_response(integration, os.environ["LIVE_DISCORD_CHANNEL_ID"], "RAG platform validation")
                return {"message_id": result.get("id")}

            await report.check("discord:post", post_discord)
    else:
        report.skipped("discord", "DISCORD_BOT_TOKEN is not in the process environment")

    if live.have("TEAMS_BOT_ID", "TEAMS_APP_PASSWORD"):
        integration = SimpleNamespace(bot_id=os.environ["TEAMS_BOT_ID"], bot_token=None)

        async def token_ok():
            token = await teams._bot_access_token(integration)
            assert len(token) > 100
            return {"token_obtained": True}

        await report.check("teams:bot-credentials", token_ok)
    else:
        report.skipped("teams", "TEAMS_BOT_ID / TEAMS_APP_PASSWORD are not in the process environment")
    return report.finish()


if __name__ == "__main__":
    sys.exit(asyncio.run(main()))
