"""
Extraction -- listing files from Box's real API, for import into a
knowledge base. Real auth shape: a real, static `BOX_API_TOKEN`, sent
as `Authorization: Bearer <token>`.
"""

import logging

import httpx

from api.config import settings

logger = logging.getLogger(__name__)

_BASE_URL = "https://api.box.com/2.0"


class BoxError(Exception):
    """Real, dedicated exception."""


class BoxRateLimitError(BoxError):
    """Real, distinguishable 429."""


async def fetch_box_files(folder_id: str = "0", limit: int = 100) -> list[dict]:
    """Real list of files from a Box folder."""
    if not settings.BOX_ENABLED:
        raise BoxError("Box integration is disabled")
    if not settings.BOX_API_TOKEN:
        raise BoxError("Box API token not configured")

    headers = {"Authorization": f"Bearer {settings.BOX_API_TOKEN}"}

    results = []
    async with httpx.AsyncClient(timeout=30.0) as client:
        response = await client.get(
            f"{_BASE_URL}/folders/{folder_id}/items",
            headers=headers,
            params={"limit": limit},
        )

        if response.status_code == 429:
            raise BoxRateLimitError("Box rate limit reached")
        if response.status_code != 200:
            raise BoxError(f"Box fetch failed: {response.status_code}")

        for entry in response.json().get("entries", []):
            if entry.get("type") != "file":
                continue
            text_parts = [
                f"File: {entry.get('name', '')}",
                f"ID: {entry.get('id', '')}",
            ]
            results.append({
                "id": entry.get("id"),
                "name": entry.get("name"),
                "text": "\n".join(text_parts),
            })

    return results
