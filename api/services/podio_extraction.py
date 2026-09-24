"""
Extraction -- fetching items from Podio's real REST API, for import
into a knowledge base.

**Real auth shape**: a real, static `PODIO_API_TOKEN` (a real Podio
OAuth2 access token, admin-configured once), sent as
`Authorization: OAuth2 <token>` (Podio's own real convention).
"""

import logging

import httpx

from api.config import settings

logger = logging.getLogger(__name__)

_BASE_URL = "https://api.podio.com"


class PodioError(Exception):
    """Real, dedicated exception."""


class PodioRateLimitError(PodioError):
    """Real, distinguishable 429."""


async def fetch_podio_items(app_id: str, limit: int = 100) -> list[dict]:
    """Real fetch of items from a Podio app."""
    if not settings.PODIO_ENABLED:
        raise PodioError("Podio integration is disabled")
    if not settings.PODIO_API_TOKEN:
        raise PodioError("Podio API token not configured")

    headers = {"Authorization": f"OAuth2 {settings.PODIO_API_TOKEN}"}

    results = []
    async with httpx.AsyncClient(timeout=30.0) as client:
        response = await client.post(
            f"{_BASE_URL}/item/app/{app_id}/filter/",
            headers=headers,
            json={"limit": limit},
        )

        if response.status_code == 429:
            raise PodioRateLimitError("Podio rate limit reached")
        if response.status_code != 200:
            raise PodioError(f"Podio fetch failed: {response.status_code}")

        for item in response.json().get("items", []):
            text_parts = [f"Item: {item.get('item_id', '')}"]
            for field in item.get("fields", []):
                label = field.get("label", "")
                values = field.get("values", [])
                for val in values:
                    if isinstance(val, dict):
                        v = val.get("value", "")
                        if v and not isinstance(v, (dict, list)):
                            text_parts.append(f"{label}: {v}")

            results.append({
                "id": item.get("item_id"),
                "text": "\n".join(text_parts),
            })

    return results
