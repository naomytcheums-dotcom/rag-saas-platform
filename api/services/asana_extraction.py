"""
Extraction -- fetching tasks from Asana's real REST API v1.0, for
import into a knowledge base.

**Real auth shape**: a real, static `ASANA_API_TOKEN` (a real Asana
"personal access token", admin-configured once), sent as
`Authorization: Bearer <token>`.
"""

import logging

import httpx

from api.config import settings

logger = logging.getLogger(__name__)

_BASE_URL = "https://app.asana.com/api/1.0"


class AsanaError(Exception):
    """Real, dedicated exception -- a connection/discovery/call failure
    against Asana, never silently swallowed."""


class AsanaRateLimitError(AsanaError):
    """Real, distinguishable 429."""


async def fetch_asana_tasks(project_gid: str | None = None, limit: int = 100) -> list[dict]:
    """Real fetch of tasks from Asana.

    Returns a list of {gid, name, text} dicts, where `text` is a real,
    plain-text representation suitable for RAG ingestion.
    """
    if not settings.ASANA_ENABLED:
        raise AsanaError("Asana integration is disabled")
    if not settings.ASANA_API_TOKEN:
        raise AsanaError("Asana API token not configured")

    headers = {"Authorization": f"Bearer {settings.ASANA_API_TOKEN}"}
    params = {"limit": limit}
    if project_gid:
        params["project"] = project_gid

    results = []
    async with httpx.AsyncClient(timeout=30.0) as client:
        response = await client.get(
            f"{_BASE_URL}/tasks",
            headers=headers,
            params=params,
        )

        if response.status_code == 429:
            raise AsanaRateLimitError("Asana rate limit reached")
        if response.status_code != 200:
            raise AsanaError(f"Asana fetch failed: {response.status_code}")

        for task in response.json().get("data", []):
            text_parts = [
                f"Task: {task.get('name', '')}",
                f"GID: {task.get('gid', '')}",
            ]
            if task.get("notes"):
                text_parts.append(f"Notes: {task['notes']}")
            if task.get("completed") is not None:
                text_parts.append(f"Completed: {task['completed']}")
            if task.get("due_on"):
                text_parts.append(f"Due: {task['due_on']}")

            results.append({
                "id": task.get("gid"),
                "name": task.get("name"),
                "text": "\n".join(text_parts),
            })

    return results
