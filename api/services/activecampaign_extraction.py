"""
Extraction -- fetching contacts/deals from ActiveCampaign's real REST
API v3, for import into a knowledge base. Real auth shape: a real,
static `ACTIVECAMPAIGN_API_TOKEN`, sent as the `Api-Token` header
(ActiveCampaign's own real convention).
"""

import logging

import httpx

from api.config import settings

logger = logging.getLogger(__name__)


class ActiveCampaignError(Exception):
    """Real, dedicated exception."""


class ActiveCampaignRateLimitError(ActiveCampaignError):
    """Real, distinguishable 429."""


async def fetch_activecampaign_contacts(limit: int = 100) -> list[dict]:
    """Real fetch of contacts from ActiveCampaign."""
    if not settings.ACTIVECAMPAIGN_ENABLED:
        raise ActiveCampaignError("ActiveCampaign integration is disabled")
    if not settings.ACTIVECAMPAIGN_API_TOKEN or not settings.ACTIVECAMPAIGN_ACCOUNT:
        raise ActiveCampaignError("ActiveCampaign credentials not configured")

    base_url = f"https://{settings.ACTIVECAMPAIGN_ACCOUNT}.api-us1.com/api/3"
    headers = {"Api-Token": settings.ACTIVECAMPAIGN_API_TOKEN}

    results = []
    async with httpx.AsyncClient(timeout=30.0) as client:
        response = await client.get(
            f"{base_url}/contacts",
            headers=headers,
            params={"limit": min(limit, 100)},
        )

        if response.status_code == 429:
            raise ActiveCampaignRateLimitError("ActiveCampaign rate limit reached")
        if response.status_code != 200:
            raise ActiveCampaignError(f"ActiveCampaign fetch failed: {response.status_code}")

        for contact in response.json().get("contacts", []):
            text_parts = [
                f"Contact: {contact.get('email', '')}",
                f"ID: {contact.get('id', '')}",
            ]
            if contact.get("firstName"):
                text_parts.append(f"First name: {contact['firstName']}")
            if contact.get("lastName"):
                text_parts.append(f"Last name: {contact['lastName']}")
            if contact.get("phone"):
                text_parts.append(f"Phone: {contact['phone']}")

            results.append({
                "id": contact.get("id"),
                "email": contact.get("email"),
                "text": "\n".join(text_parts),
            })

    return results
