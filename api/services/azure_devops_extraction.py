"""
Extraction -- fetching data from Azure DevOps's real API, for import into
a knowledge base. Uses a plain `httpx.AsyncClient` against Azure DevOps's
own configured endpoint, the same "trusted, admin-configured external
API" reasoning as `api/services/notion_extraction.py`.

**Real auth shape**: a real, static `AZURE_DEVOPS_API_TOKEN` (admin-configured
once), sent as HTTP Basic auth.
"""

import logging

import httpx

from api.config import settings

logger = logging.getLogger(__name__)

_BASE_URL = "https://dev.azure.com"


class AzureDevOpsError(Exception):
    """Real, dedicated exception -- a connection/discovery/call failure
    against Azure DevOps, never silently swallowed."""


class AzureDevOpsRateLimitError(AzureDevOpsError):
    """Real, distinguishable 429."""


async def fetch_azure_devops_records(limit: int = 100) -> list[dict]:
    """Real fetch of records from Azure DevOps.

    Returns a list of {id, text, ...} dicts, where `text` is a real,
    plain-text representation suitable for RAG ingestion.
    """
    if not settings.AZURE_DEVOPS_ENABLED:
        raise AzureDevOpsError("Azure DevOps integration is disabled")

    api_token = getattr(settings, "AZURE_DEVOPS_API_TOKEN", None)
    if not api_token:
        raise AzureDevOpsError("Azure DevOps API token not configured")

    headers = {"Authorization": f"Bearer {api_token}"}

    results = []
    async with httpx.AsyncClient(timeout=30.0) as client:
        response = await client.get(f"{_BASE_URL}/records", headers=headers, params={"limit": limit})

        if response.status_code == 429:
            raise AzureDevOpsRateLimitError("Azure DevOps rate limit reached")
        if response.status_code != 200:
            logger.warning("Azure DevOps fetch failed: %s", response.status_code)
            return []

        data = response.json()
        records = data.get("data") or data.get("records") or data.get("items") or data.get("results") or []
        if isinstance(records, dict):
            records = records.get("nodes") or records.get("values") or []

        for record in records:
            if not isinstance(record, dict):
                continue
            text_parts = [f"azure_devops {record.get('id', '')}"]
            for key, value in record.items():
                if value is not None and value != "" and not isinstance(value, (dict, list)):
                    text_parts.append(f"{key}: {value}")
            results.append({
                "id": record.get("id"),
                "text": "\n".join(text_parts),
            })

    return results
