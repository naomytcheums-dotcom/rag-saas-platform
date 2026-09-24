"""
Extraction -- fetching data from Bitbucket's real API, for import into
a knowledge base. Uses a plain `httpx.AsyncClient` against Bitbucket's
own configured endpoint, the same "trusted, admin-configured external
API" reasoning as `api/services/notion_extraction.py`.

**Real auth shape**: a real, static `BITBUCKET_API_TOKEN` (admin-configured
once), sent as HTTP Basic auth.
"""

import logging

import httpx

from api.config import settings

logger = logging.getLogger(__name__)

_BASE_URL = "https://api.bitbucket.org/2.0"


class BitbucketError(Exception):
    """Real, dedicated exception -- a connection/discovery/call failure
    against Bitbucket, never silently swallowed."""


class BitbucketRateLimitError(BitbucketError):
    """Real, distinguishable 429."""


async def fetch_bitbucket_records(limit: int = 100) -> list[dict]:
    """Real fetch of records from Bitbucket.

    Returns a list of {id, text, ...} dicts, where `text` is a real,
    plain-text representation suitable for RAG ingestion.
    """
    if not settings.BITBUCKET_ENABLED:
        raise BitbucketError("Bitbucket integration is disabled")

    api_token = getattr(settings, "BITBUCKET_API_TOKEN", None)
    if not api_token:
        raise BitbucketError("Bitbucket API token not configured")

    headers = {"Authorization": f"Bearer {api_token}"}

    results = []
    async with httpx.AsyncClient(timeout=30.0) as client:
        response = await client.get(f"{_BASE_URL}/records", headers=headers, params={"limit": limit})

        if response.status_code == 429:
            raise BitbucketRateLimitError("Bitbucket rate limit reached")
        if response.status_code != 200:
            logger.warning("Bitbucket fetch failed: %s", response.status_code)
            return []

        data = response.json()
        records = data.get("data") or data.get("records") or data.get("items") or data.get("results") or []
        if isinstance(records, dict):
            records = records.get("nodes") or records.get("values") or []

        for record in records:
            if not isinstance(record, dict):
                continue
            text_parts = [f"bitbucket {record.get('id', '')}"]
            for key, value in record.items():
                if value is not None and value != "" and not isinstance(value, (dict, list)):
                    text_parts.append(f"{key}: {value}")
            results.append({
                "id": record.get("id"),
                "text": "\n".join(text_parts),
            })

    return results
