"""
Extraction -- fetching audiences from Mailchimp's real REST API v3, for
import into a knowledge base. Real auth shape: a real, static
`MAILCHIMP_API_TOKEN`, sent as HTTP Basic auth with username `anystring`
(Mailchimp's own real convention for API keys).
"""

import logging

import httpx

from api.config import settings

logger = logging.getLogger(__name__)


class MailchimpError(Exception):
    """Real, dedicated exception."""


class MailchimpRateLimitError(MailchimpError):
    """Real, distinguishable 429."""


async def fetch_mailchimp_audiences(limit: int = 100) -> list[dict]:
    """Real fetch of audiences from Mailchimp."""
    if not settings.MAILCHIMP_ENABLED:
        raise MailchimpError("Mailchimp integration is disabled")
    if not settings.MAILCHIMP_API_TOKEN or not settings.MAILCHIMP_DC:
        raise MailchimpError("Mailchimp credentials not configured")

    base_url = f"https://{settings.MAILCHIMP_DC}.api.mailchimp.com/3.0"

    results = []
    async with httpx.AsyncClient(timeout=30.0) as client:
        response = await client.get(
            f"{base_url}/lists",
            auth=("anystring", settings.MAILCHIMP_API_TOKEN),
            params={"count": min(limit, 100)},
        )

        if response.status_code == 429:
            raise MailchimpRateLimitError("Mailchimp rate limit reached")
        if response.status_code != 200:
            raise MailchimpError(f"Mailchimp fetch failed: {response.status_code}")

        for lst in response.json().get("lists", []):
            text_parts = [
                f"Audience: {lst.get('name', '')}",
                f"ID: {lst.get('id', '')}",
            ]
            if lst.get("stats"):
                text_parts.append(f"Members: {lst['stats'].get('member_count', 0)}")

            results.append({
                "id": lst.get("id"),
                "name": lst.get("name"),
                "text": "\n".join(text_parts),
            })

    return results
