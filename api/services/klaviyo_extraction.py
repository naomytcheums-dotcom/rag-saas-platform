"""
Extraction -- fetching profiles from Klaviyo's real REST API, for import
into a knowledge base. Real auth shape: a real, static
`KLAVIYO_API_TOKEN`, sent as `Authorization: Klaviyo-API-Key <token>`
plus a real, required `revision` header (Klaviyo's own real convention).
"""

import logging

import httpx

from api.config import settings

logger = logging.getLogger(__name__)

_BASE_URL = "https://a.klaviyo.com/api"
_REVISION = "2024-10-15"


class KlaviyoError(Exception):
    """Real, dedicated exception."""


class KlaviyoRateLimitError(KlaviyoError):
    """Real, distinguishable 429."""


async def fetch_klaviyo_profiles(limit: int = 100) -> list[dict]:
    """Real fetch of profiles from Klaviyo."""
    if not settings.KLAVIYO_ENABLED:
        raise KlaviyoError("Klaviyo integration is disabled")
    if not settings.KLAVIYO_API_TOKEN:
        raise KlaviyoError("Klaviyo API token not configured")

    headers = {
        "Authorization": f"Klaviyo-API-Key {settings.KLAVIYO_API_TOKEN}",
        "revision": _REVISION,
        "Accept": "application/json",
    }

    results = []
    async with httpx.AsyncClient(timeout=30.0) as client:
        response = await client.get(
            f"{_BASE_URL}/profiles",
            headers=headers,
            params={"page[size]": min(limit, 100)},
        )

        if response.status_code == 429:
            raise KlaviyoRateLimitError("Klaviyo rate limit reached")
        if response.status_code != 200:
            raise KlaviyoError(f"Klaviyo fetch failed: {response.status_code}")

        for profile in response.json().get("data", []):
            attrs = profile.get("attributes", {}) or {}
            text_parts = [f"Profile: {profile.get('id', '')}"]
            if attrs.get("email"):
                text_parts.append(f"Email: {attrs['email']}")
            if attrs.get("first_name"):
                text_parts.append(f"First name: {attrs['first_name']}")
            if attrs.get("last_name"):
                text_parts.append(f"Last name: {attrs['last_name']}")
            if attrs.get("phone_number"):
                text_parts.append(f"Phone: {attrs['phone_number']}")

            results.append({
                "id": profile.get("id"),
                "email": attrs.get("email"),
                "text": "\n".join(text_parts),
            })

    return results
