"""
Extraction -- fetching records from Airtable's real REST API v0, for
import into a knowledge base.

**Real auth shape**: a real, static `AIRTABLE_API_TOKEN` (a real
Airtable "personal access token", admin-configured once), sent as
`Authorization: Bearer <token>`.
"""

import logging

import httpx

from api.config import settings

logger = logging.getLogger(__name__)

_BASE_URL = "https://api.airtable.com/v0"


class AirtableError(Exception):
    """Real, dedicated exception -- a connection/discovery/call failure
    against Airtable, never silently swallowed."""


class AirtableRateLimitError(AirtableError):
    """Real, distinguishable 429."""


async def fetch_airtable_records(
    base_id: str,
    table_name: str,
    limit: int = 100,
) -> list[dict]:
    """Real fetch of records from an Airtable table.

    Returns a list of {id, fields, text} dicts, where `text` is a real,
    plain-text representation suitable for RAG ingestion.
    """
    if not settings.AIRTABLE_ENABLED:
        raise AirtableError("Airtable integration is disabled")
    if not settings.AIRTABLE_API_TOKEN:
        raise AirtableError("Airtable API token not configured")

    headers = {"Authorization": f"Bearer {settings.AIRTABLE_API_TOKEN}"}

    results = []
    async with httpx.AsyncClient(timeout=30.0) as client:
        response = await client.get(
            f"{_BASE_URL}/{base_id}/{table_name}",
            headers=headers,
            params={"maxRecords": limit},
        )

        if response.status_code == 429:
            raise AirtableRateLimitError("Airtable rate limit reached")
        if response.status_code != 200:
            raise AirtableError(f"Airtable fetch failed: {response.status_code}")

        for record in response.json().get("records", []):
            fields = record.get("fields", {}) or {}
            text_parts = [f"Record: {record.get('id', '')}"]
            for key, value in fields.items():
                if value is not None and value != "":
                    text_parts.append(f"{key}: {value}")

            results.append({
                "id": record.get("id"),
                "fields": fields,
                "text": "\n".join(text_parts),
            })

    return results
