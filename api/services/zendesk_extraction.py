"""
CRM extraction -- fetching tickets from Zendesk's real REST API v2, for
import into a knowledge base. Uses a plain `httpx.AsyncClient` against
the org's own configured Zendesk subdomain, the same "trusted,
admin-configured external API" reasoning as
`api/services/notion_extraction.py`.

**Real auth shape**: a real, static `ZENDESK_EMAIL` + `ZENDESK_API_TOKEN`
pair, sent as `Authorization: Bearer` -- no OAuth refresh dance needed.
"""

import logging

import httpx

from api.config import settings

logger = logging.getLogger(__name__)


class ZendeskError(Exception):
    """Real, dedicated exception -- a connection/discovery/call failure
    against Zendesk, never silently swallowed."""


class ZendeskRateLimitError(ZendeskError):
    """Real, distinguishable 429."""


async def fetch_zendesk_tickets(limit: int = 100) -> list[dict]:
    """Real fetch of tickets from Zendesk.

    Returns a list of {id, subject, status, text} dicts, where `text` is
    a real, plain-text representation suitable for RAG ingestion.
    """
    if not settings.ZENDESK_ENABLED:
        raise ZendeskError("Zendesk integration is disabled")
    if not settings.ZENDESK_SUBDOMAIN or not settings.ZENDESK_EMAIL or not settings.ZENDESK_API_TOKEN:
        raise ZendeskError("Zendesk credentials not configured")

    headers = {"Authorization": f"Bearer {settings.ZENDESK_API_TOKEN}"}
    base_url = f"https://{settings.ZENDESK_SUBDOMAIN}.zendesk.com/api/v2"

    results = []
    async with httpx.AsyncClient(timeout=30.0) as client:
        response = await client.get(
            f"{base_url}/tickets.json",
            headers=headers,
            params={"per_page": limit},
        )

        if response.status_code == 429:
            raise ZendeskRateLimitError("Zendesk rate limit reached")
        if response.status_code != 200:
            raise ZendeskError(f"Zendesk fetch failed: {response.status_code}")

        for ticket in response.json().get("tickets", []):
            text_parts = [
                f"Ticket #{ticket.get('id', '')}",
                f"Subject: {ticket.get('subject', '')}",
                f"Status: {ticket.get('status', '')}",
                f"Priority: {ticket.get('priority', '')}",
            ]
            if ticket.get("description"):
                text_parts.append(f"Description: {ticket['description']}")

            results.append({
                "id": ticket.get("id"),
                "subject": ticket.get("subject"),
                "status": ticket.get("status"),
                "text": "\n".join(text_parts),
            })

    return results
