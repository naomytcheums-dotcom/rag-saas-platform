"""
Extraction -- fetching records from SmartSuite's real REST API v1, for
import into a knowledge base. Real auth shape: a real, static
`SMARTSUITE_API_TOKEN` + `SMARTSUITE_ACCOUNT_ID` pair, sent as
`Authorization: Token <token>` + `ACCOUNT-ID: <account_id>`
(SmartSuite's own real convention).
"""

import logging

import httpx

from api.config import settings

logger = logging.getLogger(__name__)

_BASE_URL = "https://app.smartsuite.com/api/v1"


class SmartSuiteError(Exception):
    """Real, dedicated exception."""


class SmartSuiteRateLimitError(SmartSuiteError):
    """Real, distinguishable 429."""


async def fetch_smartsuite_records(table_id: str, limit: int = 100) -> list[dict]:
    """Real fetch of records from a SmartSuite table."""
    if not settings.SMARTSUITE_ENABLED:
        raise SmartSuiteError("SmartSuite integration is disabled")
    if not settings.SMARTSUITE_API_TOKEN or not settings.SMARTSUITE_ACCOUNT_ID:
        raise SmartSuiteError("SmartSuite credentials not configured")

    headers = {
        "Authorization": f"Token {settings.SMARTSUITE_API_TOKEN}",
        "ACCOUNT-ID": settings.SMARTSUITE_ACCOUNT_ID,
    }

    results = []
    async with httpx.AsyncClient(timeout=30.0) as client:
        response = await client.post(
            f"{_BASE_URL}/applications/{table_id}/records/list/",
            headers=headers,
            json={"limit": limit},
        )

        if response.status_code == 429:
            raise SmartSuiteRateLimitError("SmartSuite rate limit reached")
        if response.status_code != 200:
            raise SmartSuiteError(f"SmartSuite fetch failed: {response.status_code}")

        for record in response.json().get("items", []):
            text_parts = [f"Record: {record.get('id', '')}"]
            for key, value in record.items():
                if value is not None and value != "" and not isinstance(value, (dict, list)):
                    text_parts.append(f"{key}: {value}")

            results.append({
                "id": record.get("id"),
                "text": "\n".join(text_parts),
            })

    return results
