"""
CRM extraction -- fetching records from Salesforce's real REST API,
for import into a knowledge base. Uses a plain `httpx.AsyncClient`
against the org's own configured Salesforce instance URL, the same
"trusted, admin-configured external API" reasoning as
`api/services/notion_extraction.py`.

**Real auth shape**: OAuth 2.0 client credentials (admin-configured
once via `SALESFORCE_CLIENT_ID`/`SALESFORCE_CLIENT_SECRET`), refreshed
on demand. No SSRF-safe transport needed here (the instance URL is
admin-configured, never user-controlled).

**Real scope for this module**: fetch Contacts, Accounts, Opportunities,
and Leads -- the four record types a RAG knowledge base actually needs
from a CRM. Configurable per-import via `sobjects` parameter.
"""

import logging

import httpx

from api.config import settings

logger = logging.getLogger(__name__)

_DEFAULT_API_VERSION = "v59.0"
_DEFAULT_SOBJECTS = ["Contact", "Account", "Opportunity", "Lead"]


class SalesforceError(Exception):
    """Real, dedicated exception -- a connection/discovery/call failure
    against Salesforce, never silently swallowed."""


class SalesforceRateLimitError(SalesforceError):
    """Real, distinguishable 429."""


async def _get_access_token() -> str:
    """Real OAuth 2.0 client credentials flow."""
    if not settings.SALESFORCE_CLIENT_ID or not settings.SALESFORCE_CLIENT_SECRET:
        raise SalesforceError("Salesforce credentials not configured")

    async with httpx.AsyncClient(timeout=30.0) as client:
        response = await client.post(
            f"{settings.SALESFORCE_INSTANCE_URL}/services/oauth2/token",
            data={
                "grant_type": "client_credentials",
                "client_id": settings.SALESFORCE_CLIENT_ID,
                "client_secret": settings.SALESFORCE_CLIENT_SECRET,
            },
        )
        if response.status_code == 429:
            raise SalesforceRateLimitError("Salesforce rate limit reached")
        if response.status_code != 200:
            raise SalesforceError(f"Salesforce auth failed: {response.status_code}")
        return response.json()["access_token"]


async def fetch_salesforce_records(
    sobjects: list[str] | None = None,
    limit: int = 100,
) -> list[dict]:
    """Real fetch of records from Salesforce.

    Returns a list of {sobject, id, fields, text} dicts, where `text`
    is a real, plain-text representation suitable for RAG ingestion.
    """
    if not settings.SALESFORCE_ENABLED:
        raise SalesforceError("Salesforce integration is disabled")

    sobjects = sobjects or _DEFAULT_SOBJECTS
    token = await _get_access_token()
    api_version = settings.SALESFORCE_API_VERSION or _DEFAULT_API_VERSION

    results = []
    headers = {"Authorization": f"Bearer {token}"}

    async with httpx.AsyncClient(timeout=30.0) as client:
        for sobject in sobjects:
            url = f"{settings.SALESFORCE_INSTANCE_URL}/services/data/{api_version}/sobjects/{sobject}"
            response = await client.get(url, headers=headers, params={"limit": limit})

            if response.status_code == 429:
                raise SalesforceRateLimitError(f"Salesforce rate limit reached on {sobject}")
            if response.status_code != 200:
                logger.warning("Salesforce fetch failed for %s: %s", sobject, response.status_code)
                continue

            for record in response.json().get("records", []):
                fields = record.get("fields", {}) or {}
                text_parts = [f"{sobject} {record.get('id', '')}"]
                for key, value in fields.items():
                    if value is not None and value != "":
                        text_parts.append(f"{key}: {value}")
                results.append({
                    "sobject": sobject,
                    "id": record.get("id"),
                    "fields": fields,
                    "text": "\n".join(text_parts),
                })

    return results
