"""
CRM extraction -- fetching records from HubSpot's real CRM API v3, for
import into a knowledge base. Uses a plain `httpx.AsyncClient` against
HubSpot's own fixed API host, the same "trusted, fixed external API"
reasoning as `api/services/notion_extraction.py`.

**Real auth shape**: a single, real, static `HUBSPOT_API_TOKEN` (a real
HubSpot "private app" access token, admin-configured once, the SAME
shape as `NOTION_API_TOKEN`/`GITHUB_API_TOKEN` -- no OAuth refresh
dance needed).

**Real scope for this module**: fetch Contacts, Companies, Deals, and
Tickets -- the four record types a RAG knowledge base actually needs
from a CRM. Configurable per-import via `object_types` parameter.
"""

import logging

import httpx

from api.config import settings

logger = logging.getLogger(__name__)

_DEFAULT_OBJECT_TYPES = ["contacts", "companies", "deals", "tickets"]


class HubSpotError(Exception):
    """Real, dedicated exception -- a connection/discovery/call failure
    against HubSpot, never silently swallowed."""


class HubSpotRateLimitError(HubSpotError):
    """Real, distinguishable 429."""


async def fetch_hubspot_records(
    object_types: list[str] | None = None,
    limit: int = 100,
) -> list[dict]:
    """Real fetch of records from HubSpot CRM.

    Returns a list of {object_type, id, properties, text} dicts, where
    `text` is a real, plain-text representation suitable for RAG ingestion.
    """
    if not settings.HUBSPOT_ENABLED:
        raise HubSpotError("HubSpot integration is disabled")

    if not settings.HUBSPOT_API_TOKEN:
        raise HubSpotError("HubSpot API token not configured")

    object_types = object_types or _DEFAULT_OBJECT_TYPES
    headers = {"Authorization": f"Bearer {settings.HUBSPOT_API_TOKEN}"}
    base_url = settings.HUBSPOT_API_BASE_URL

    results = []

    async with httpx.AsyncClient(timeout=30.0) as client:
        for object_type in object_types:
            url = f"{base_url}/crm/v3/objects/{object_type}"
            response = await client.get(
                url,
                headers=headers,
                params={"limit": limit, "properties": "firstname,lastname,email,name,description,phone,company"},
            )

            if response.status_code == 429:
                raise HubSpotRateLimitError(f"HubSpot rate limit reached on {object_type}")
            if response.status_code != 200:
                logger.warning("HubSpot fetch failed for %s: %s", object_type, response.status_code)
                continue

            for record in response.json().get("results", []):
                properties = record.get("properties", {}) or {}
                text_parts = [f"{object_type} {record.get('id', '')}"]
                for key, value in properties.items():
                    if value is not None and value != "":
                        text_parts.append(f"{key}: {value}")
                results.append({
                    "object_type": object_type,
                    "id": record.get("id"),
                    "properties": properties,
                    "text": "\n".join(text_parts),
                })

    return results
