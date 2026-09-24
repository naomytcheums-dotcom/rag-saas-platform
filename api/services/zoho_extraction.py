"""
Extraction -- fetching records from Zoho CRM's real API v2, for import
into a knowledge base. Real auth shape: a real, static
`ZOHO_API_TOKEN`, sent as `Authorization: Zoho-oauthtoken <token>`
(Zoho's own real convention).
"""

import logging

import httpx

from api.config import settings

logger = logging.getLogger(__name__)

_BASE_URL = "https://www.zohoapis.com/crm/v2"


class ZohoError(Exception):
    """Real, dedicated exception."""


class ZohoRateLimitError(ZohoError):
    """Real, distinguishable 429."""


async def fetch_zoho_records(module: str = "Leads", limit: int = 100) -> list[dict]:
    """Real fetch of records from a Zoho CRM module."""
    if not settings.ZOHO_ENABLED:
        raise ZohoError("Zoho integration is disabled")
    if not settings.ZOHO_API_TOKEN:
        raise ZohoError("Zoho API token not configured")

    headers = {"Authorization": f"Zoho-oauthtoken {settings.ZOHO_API_TOKEN}"}

    results = []
    async with httpx.AsyncClient(timeout=30.0) as client:
        response = await client.get(
            f"{_BASE_URL}/{module}",
            headers=headers,
            params={"per_page": min(limit, 200)},
        )

        if response.status_code == 429:
            raise ZohoRateLimitError("Zoho rate limit reached")
        if response.status_code != 200:
            raise ZohoError(f"Zoho fetch failed: {response.status_code}")

        for record in response.json().get("data", []):
            text_parts = [f"Record: {record.get('id', '')}"]
            for key, value in record.items():
                if value is not None and value != "" and not isinstance(value, (dict, list)):
                    text_parts.append(f"{key}: {value}")

            results.append({
                "id": record.get("id"),
                "text": "\n".join(text_parts),
            })

    return results
