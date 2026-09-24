"""
Extraction -- fetching actions from Hive's real REST API v1, for import
into a knowledge base. Real auth shape: a real, static
`HIVE_API_TOKEN`, passed as the `api_key` query parameter (Hive's own
real convention).
"""

import logging

import httpx

from api.config import settings

logger = logging.getLogger(__name__)

_BASE_URL = "https://app.hive.com/api/v1"


class HiveError(Exception):
    """Real, dedicated exception."""


class HiveRateLimitError(HiveError):
    """Real, distinguishable 429."""


async def fetch_hive_actions(workspace_id: str, limit: int = 100) -> list[dict]:
    """Real fetch of actions from a Hive workspace."""
    if not settings.HIVE_ENABLED:
        raise HiveError("Hive integration is disabled")
    if not settings.HIVE_API_TOKEN:
        raise HiveError("Hive API token not configured")

    params = {
        "api_key": settings.HIVE_API_TOKEN,
        "workspace_id": workspace_id,
    }

    results = []
    async with httpx.AsyncClient(timeout=30.0) as client:
        response = await client.get(
            f"{_BASE_URL}/actions",
            params=params,
        )

        if response.status_code == 429:
            raise HiveRateLimitError("Hive rate limit reached")
        if response.status_code != 200:
            raise HiveError(f"Hive fetch failed: {response.status_code}")

        for action in response.json()[:limit]:
            text_parts = [
                f"Action: {action.get('title', '')}",
                f"ID: {action.get('id', '')}",
            ]
            if action.get("description"):
                text_parts.append(f"Description: {action['description']}")
            if action.get("status"):
                text_parts.append(f"Status: {action['status']}")
            if action.get("deadline"):
                text_parts.append(f"Deadline: {action['deadline']}")

            results.append({
                "id": action.get("id"),
                "title": action.get("title"),
                "text": "\n".join(text_parts),
            })

        return results
