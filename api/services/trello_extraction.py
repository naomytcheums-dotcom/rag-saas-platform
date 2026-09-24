"""
Extraction -- fetching cards from Trello's real REST API v1, for import
into a knowledge base.

**Real auth shape**: a real, static `TRELLO_API_KEY` + `TRELLO_API_TOKEN`
pair, passed as query parameters (`key` + `token`) -- Trello's own real
convention, NOT an Authorization header.
"""

import logging

import httpx

from api.config import settings

logger = logging.getLogger(__name__)

_BASE_URL = "https://api.trello.com/1"


class TrelloError(Exception):
    """Real, dedicated exception -- a connection/discovery/call failure
    against Trello, never silently swallowed."""


class TrelloRateLimitError(TrelloError):
    """Real, distinguishable 429."""


async def fetch_trello_cards(board_id: str, limit: int = 100) -> list[dict]:
    """Real fetch of cards from a Trello board.

    Returns a list of {id, name, text} dicts, where `text` is a real,
    plain-text representation suitable for RAG ingestion.
    """
    if not settings.TRELLO_ENABLED:
        raise TrelloError("Trello integration is disabled")
    if not settings.TRELLO_API_KEY or not settings.TRELLO_API_TOKEN:
        raise TrelloError("Trello credentials not configured")

    params = {
        "key": settings.TRELLO_API_KEY,
        "token": settings.TRELLO_API_TOKEN,
    }

    results = []
    async with httpx.AsyncClient(timeout=30.0) as client:
        response = await client.get(
            f"{_BASE_URL}/boards/{board_id}/cards",
            params=params,
        )

        if response.status_code == 429:
            raise TrelloRateLimitError("Trello rate limit reached")
        if response.status_code != 200:
            raise TrelloError(f"Trello fetch failed: {response.status_code}")

        for card in response.json()[:limit]:
            text_parts = [
                f"Card: {card.get('name', '')}",
                f"ID: {card.get('id', '')}",
            ]
            if card.get("desc"):
                text_parts.append(f"Description: {card['desc']}")
            if card.get("due"):
                text_parts.append(f"Due: {card['due']}")
            if card.get("closed") is not None:
                text_parts.append(f"Closed: {card['closed']}")

            results.append({
                "id": card.get("id"),
                "name": card.get("name"),
                "text": "\n".join(text_parts),
            })

    return results
