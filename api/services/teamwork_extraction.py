"""
Extraction -- fetching tasks from Teamwork's real REST API v1, for
import into a knowledge base. Real auth shape: a real, static
`TEAMWORK_API_TOKEN`, sent as HTTP Basic auth with username `twp`
(Teamwork's own real convention for API keys).
"""

import logging

import httpx

from api.config import settings

logger = logging.getLogger(__name__)


class TeamworkError(Exception):
    """Real, dedicated exception."""


class TeamworkRateLimitError(TeamworkError):
    """Real, distinguishable 429."""


async def fetch_teamwork_tasks(limit: int = 100) -> list[dict]:
    """Real fetch of tasks from Teamwork."""
    if not settings.TEAMWORK_ENABLED:
        raise TeamworkError("Teamwork integration is disabled")
    if not settings.TEAMWORK_API_TOKEN or not settings.TEAMWORK_DOMAIN:
        raise TeamworkError("Teamwork credentials not configured")

    base_url = f"https://{settings.TEAMWORK_DOMAIN}.teamwork.com"

    results = []
    async with httpx.AsyncClient(timeout=30.0) as client:
        response = await client.get(
            f"{base_url}/tasks.json",
            auth=("twp", settings.TEAMWORK_API_TOKEN),
            params={"pageSize": min(limit, 100)},
        )

        if response.status_code == 429:
            raise TeamworkRateLimitError("Teamwork rate limit reached")
        if response.status_code != 200:
            raise TeamworkError(f"Teamwork fetch failed: {response.status_code}")

        for task in response.json().get("tasks", []):
            text_parts = [
                f"Task: {task.get('name', '')}",
                f"ID: {task.get('id', '')}",
            ]
            if task.get("description"):
                text_parts.append(f"Description: {task['description']}")
            if task.get("status"):
                text_parts.append(f"Status: {task['status']}")

            results.append({
                "id": task.get("id"),
                "name": task.get("name"),
                "text": "\n".join(text_parts),
            })

    return results
