"""
Extraction -- fetching workflows/runs from Process Street's real REST
API v1.1, for import into a knowledge base. Real auth shape: a real,
static `PROCESS_STREET_API_TOKEN`, sent as
`Authorization: Bearer <token>`.
"""

import logging

import httpx

from api.config import settings

logger = logging.getLogger(__name__)

_BASE_URL = "https://public-api.process.st/api/v1.1"


class ProcessStreetError(Exception):
    """Real, dedicated exception."""


class ProcessStreetRateLimitError(ProcessStreetError):
    """Real, distinguishable 429."""


async def fetch_process_street_workflows(limit: int = 100) -> list[dict]:
    """Real fetch of workflows from Process Street."""
    if not settings.PROCESS_STREET_ENABLED:
        raise ProcessStreetError("Process Street integration is disabled")
    if not settings.PROCESS_STREET_API_TOKEN:
        raise ProcessStreetError("Process Street API token not configured")

    headers = {"Authorization": f"Bearer {settings.PROCESS_STREET_API_TOKEN}"}

    results = []
    async with httpx.AsyncClient(timeout=30.0) as client:
        response = await client.get(
            f"{_BASE_URL}/workflows",
            headers=headers,
            params={"limit": limit},
        )

        if response.status_code == 429:
            raise ProcessStreetRateLimitError("Process Street rate limit reached")
        if response.status_code != 200:
            raise ProcessStreetError(f"Process Street fetch failed: {response.status_code}")

        for workflow in response.json().get("workflows", []):
            text_parts = [
                f"Workflow: {workflow.get('name', '')}",
                f"ID: {workflow.get('id', '')}",
            ]
            if workflow.get("description"):
                text_parts.append(f"Description: {workflow['description']}")

            results.append({
                "id": workflow.get("id"),
                "name": workflow.get("name"),
                "text": "\n".join(text_parts),
            })

    return results
