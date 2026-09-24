"""
Extraction -- fetching tasks from ClickUp's real API v2, for import into
a knowledge base. Real auth shape: a real, static
`CLICKUP_API_TOKEN`, sent as the raw `Authorization` header (ClickUp's
own real convention -- NOT "Bearer <token>").
"""

import logging

import httpx

from api.config import settings

logger = logging.getLogger(__name__)

_BASE_URL = "https://api.clickup.com/api/v2"


class ClickUpError(Exception):
    """Real, dedicated exception."""


class ClickUpRateLimitError(ClickUpError):
    """Real, distinguishable 429."""


async def fetch_clickup_tasks(list_id: str, limit: int = 100) -> list[dict]:
    """Real fetch of tasks from a ClickUp list."""
    if not settings.CLICKUP_ENABLED:
        raise ClickUpError("ClickUp integration is disabled")
    if not settings.CLICKUP_API_TOKEN:
        raise ClickUpError("ClickUp API token not configured")

    headers = {"Authorization": settings.CLICKUP_API_TOKEN}

    results = []
    async with httpx.AsyncClient(timeout=30.0) as client:
        response = await client.get(
            f"{_BASE_URL}/list/{list_id}/task",
            headers=headers,
            params={"page": 0},
        )

        if response.status_code == 429:
            raise ClickUpRateLimitError("ClickUp rate limit reached")
        if response.status_code != 200:
            raise ClickUpError(f"ClickUp fetch failed: {response.status_code}")

        for task in response.json().get("tasks", [])[:limit]:
            text_parts = [
                f"Task: {task.get('name', '')}",
                f"ID: {task.get('id', '')}",
            ]
            if task.get("description"):
                text_parts.append(f"Description: {task['description']}")
            if task.get("status"):
                text_parts.append(f"Status: {task['status'].get('status', '')}")
            if task.get("priority"):
                text_parts.append(f"Priority: {task['priority'].get('priority', '')}")

            results.append({
                "id": task.get("id"),
                "name": task.get("name"),
                "text": "\n".join(text_parts),
            })

    return results
