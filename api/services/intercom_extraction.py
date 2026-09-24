"""
Extraction -- fetching conversations from Intercom's real API v1, for
import into a knowledge base. Real auth shape: a real, static
`INTERCOM_API_TOKEN`, sent as `Authorization: Bearer <token>`.
"""

import logging

import httpx

from api.config import settings

logger = logging.getLogger(__name__)

_BASE_URL = "https://api.intercom.io"


class IntercomError(Exception):
    """Real, dedicated exception."""


class IntercomRateLimitError(IntercomError):
    """Real, distinguishable 429."""


async def fetch_intercom_conversations(limit: int = 100) -> list[dict]:
    """Real fetch of conversations from Intercom."""
    if not settings.INTERCOM_ENABLED:
        raise IntercomError("Intercom integration is disabled")
    if not settings.INTERCOM_API_TOKEN:
        raise IntercomError("Intercom API token not configured")

    headers = {
        "Authorization": f"Bearer {settings.INTERCOM_API_TOKEN}",
        "Intercom-Version": "2.10",
    }

    results = []
    async with httpx.AsyncClient(timeout=30.0) as client:
        response = await client.get(
            f"{_BASE_URL}/conversations",
            headers=headers,
            params={"per_page": min(limit, 150)},
        )

        if response.status_code == 429:
            raise IntercomRateLimitError("Intercom rate limit reached")
        if response.status_code != 200:
            raise IntercomError(f"Intercom fetch failed: {response.status_code}")

        for conv in response.json().get("conversations", []):
            text_parts = [
                f"Conversation: {conv.get('id', '')}",
                f"Created: {conv.get('created_at', '')}",
            ]
            if conv.get("source"):
                text_parts.append(f"Source: {conv['source'].get('subject', '')}")

            results.append({
                "id": conv.get("id"),
                "text": "\n".join(text_parts),
            })

    return results
