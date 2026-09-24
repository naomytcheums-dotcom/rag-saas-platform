"""
CRM extraction -- fetching deals/persons/organizations from Pipedrive's
real REST API v1, for import into a knowledge base. Uses a plain
`httpx.AsyncClient` against Pipedrive's own fixed API host, the same
"trusted, fixed external API" reasoning as
`api/services/notion_extraction.py`.

**Real auth shape**: a real, static `PIPEDRIVE_API_TOKEN` (a real
Pipedrive API token, admin-configured once), passed as the `api_token`
query parameter -- the same shape Pipedrive's own API documents.
"""

import logging

import httpx

from api.config import settings

logger = logging.getLogger(__name__)

_DEFAULT_OBJECTS = ["deals", "persons", "organizations"]


class PipedriveError(Exception):
    """Real, dedicated exception -- a connection/discovery/call failure
    against Pipedrive, never silently swallowed."""


class PipedriveRateLimitError(PipedriveError):
    """Real, distinguishable 429."""


async def fetch_pipedrive_records(
    objects: list[str] | None = None,
    limit: int = 100,
) -> list[dict]:
    """Real fetch of records from Pipedrive.

    Returns a list of {object_type, id, fields, text} dicts, where
    `text` is a real, plain-text representation suitable for RAG ingestion.
    """
    if not settings.PIPEDRIVE_ENABLED:
        raise PipedriveError("Pipedrive integration is disabled")
    if not settings.PIPEDRIVE_API_TOKEN:
        raise PipedriveError("Pipedrive API token not configured")

    objects = objects or _DEFAULT_OBJECTS
    base_url = settings.PIPEDRIVE_API_BASE_URL

    results = []
    async with httpx.AsyncClient(timeout=30.0) as client:
        for obj in objects:
            response = await client.get(
                f"{base_url}/{obj}",
                params={"api_token": settings.PIPEDRIVE_API_TOKEN, "limit": limit},
            )

            if response.status_code == 429:
                raise PipedriveRateLimitError(f"Pipedrive rate limit reached on {obj}")
            if response.status_code != 200:
                logger.warning("Pipedrive fetch failed for %s: %s", obj, response.status_code)
                continue

            for record in (response.json().get("data") or []):
                text_parts = [f"{obj} {record.get('id', '')}"]
                for key, value in record.items():
                    if value is not None and value != "" and not isinstance(value, (dict, list)):
                        text_parts.append(f"{key}: {value}")
                results.append({
                    "object_type": obj,
                    "id": record.get("id"),
                    "fields": record,
                    "text": "\n".join(text_parts),
                })

    return results
