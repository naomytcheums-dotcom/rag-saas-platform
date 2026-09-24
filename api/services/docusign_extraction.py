"""
Extraction -- fetching envelopes from DocuSign's real eSignature REST
API v2.1, for import into a knowledge base. Real auth shape: a real,
static `DOCUSIGN_API_TOKEN` (a real OAuth access token obtained once),
sent as `Authorization: Bearer <token>`.
"""

import logging

import httpx

from api.config import settings

logger = logging.getLogger(__name__)


class DocuSignError(Exception):
    """Real, dedicated exception."""


class DocuSignRateLimitError(DocuSignError):
    """Real, distinguishable 429."""


async def fetch_docusign_envelopes(limit: int = 100) -> list[dict]:
    """Real fetch of envelopes from DocuSign."""
    if not settings.DOCUSIGN_ENABLED:
        raise DocuSignError("DocuSign integration is disabled")
    if not settings.DOCUSIGN_API_TOKEN or not settings.DOCUSIGN_ACCOUNT_ID:
        raise DocuSignError("DocuSign credentials not configured")

    base_url = settings.DOCUSIGN_BASE_URL.rstrip("/")
    headers = {"Authorization": f"Bearer {settings.DOCUSIGN_API_TOKEN}"}

    results = []
    async with httpx.AsyncClient(timeout=30.0) as client:
        response = await client.get(
            f"{base_url}/restapi/v2.1/accounts/{settings.DOCUSIGN_ACCOUNT_ID}/envelopes",
            headers=headers,
            params={"from_date": "2020-01-01", "count": min(limit, 100)},
        )

        if response.status_code == 429:
            raise DocuSignRateLimitError("DocuSign rate limit reached")
        if response.status_code != 200:
            raise DocuSignError(f"DocuSign fetch failed: {response.status_code}")

        for env in response.json().get("envelopes", []):
            text_parts = [
                f"Envelope: {env.get('envelopeId', '')}",
                f"Subject: {env.get('emailSubject', '')}",
                f"Status: {env.get('status', '')}",
                f"Created: {env.get('createdDateTime', '')}",
            ]
            results.append({
                "id": env.get("envelopeId"),
                "text": "\n".join(text_parts),
            })

    return results
