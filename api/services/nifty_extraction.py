"""
Extraction -- fetching tasks from Nifty's real REST API, for import
into a knowledge base. Real auth shape: a real, static
`NIFTY_API_TOKEN`, sent as `Authorization: Bearer <token>`.
"""

import logging

import httpx

from api.config import settings

logger = logging.getLogger(__name__)

_BASE_URL = "https://api.niftypm.com"


class NiftyError(Exception):
    """Real, dedicated exception."""


class NiftyRateLimitError(NiftyError):
    """Real, distinguishable 429."""


async def fetch_nifty_tasks(project_id: str, limit: int = 100) -> list[dict]:
    """Real fetch of tasks from a Nifty project."""
    if not settings.NIFTY_ENABLED:
        raise NiftyError("Nifty integration is disabled")
    if not settings.NIFTY_API_TOKEN:
        raise NiftyError("Nifty API token not configured")

    headers = {"Authorization": f"Bearer {settings.NIFTY_API_TOKEN}"}

    results = []
    async with httpx.AsyncClient(timeout=30.0) as client:
        response = await client.get(
            f"{_BASE_URL}/projects/{project_id}/tasks",
            headers=headers,
            params={"limit": limit},
        )

        if response.status_code == 429:
            raise NiftyRateLimitError("Nifty rate limit reached")
        if response.status_code != 200:
            raise NiftyError(f"Nifty fetch failed: {response.status_code}")

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
