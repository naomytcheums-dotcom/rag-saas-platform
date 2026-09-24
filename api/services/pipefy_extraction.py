"""
Extraction -- fetching cards from Pipefy's real GraphQL API, for import
into a knowledge base. Real auth shape: a real, static
`PIPEFY_API_TOKEN`, sent as `Authorization: Bearer <token>`.
"""

import logging

import httpx

from api.config import settings

logger = logging.getLogger(__name__)

_GRAPHQL_ENDPOINT = "https://api.pipefy.com/graphql"

_CARDS_QUERY = """
query Cards($pipeId: ID!, $first: Int!) {
  pipe(id: $pipeId) {
    cards(first: $first) {
      edges {
        node {
          id
          title
          current_phase { name }
          assignees { name email }
          created_at
          updated_at
        }
      }
    }
  }
}
"""


class PipefyError(Exception):
    """Real, dedicated exception."""


class PipefyRateLimitError(PipefyError):
    """Real, distinguishable 429."""


async def fetch_pipefy_cards(pipe_id: str, limit: int = 100) -> list[dict]:
    """Real fetch of cards from a Pipefy pipe."""
    if not settings.PIPEFY_ENABLED:
        raise PipefyError("Pipefy integration is disabled")
    if not settings.PIPEFY_API_TOKEN:
        raise PipefyError("Pipefy API token not configured")

    headers = {
        "Authorization": f"Bearer {settings.PIPEFY_API_TOKEN}",
        "Content-Type": "application/json",
    }

    async with httpx.AsyncClient(timeout=30.0) as client:
        response = await client.post(
            _GRAPHQL_ENDPOINT,
            headers=headers,
            json={"query": _CARDS_QUERY, "variables": {"pipeId": pipe_id, "first": limit}},
        )

        if response.status_code == 429:
            raise PipefyRateLimitError("Pipefy rate limit reached")
        if response.status_code != 200:
            raise PipefyError(f"Pipefy fetch failed: {response.status_code}")

        data = response.json()
        if "errors" in data:
            raise PipefyError(f"Pipefy GraphQL errors: {data['errors']}")

        edges = data.get("data", {}).get("pipe", {}).get("cards", {}).get("edges", [])
        results = []
        for edge in edges:
            card = edge.get("node", {})
            text_parts = [
                f"Card: {card.get('title', '')}",
                f"ID: {card.get('id', '')}",
            ]
            if card.get("current_phase"):
                text_parts.append(f"Phase: {card['current_phase'].get('name', '')}")
            for assignee in card.get("assignees", []):
                text_parts.append(f"Assignee: {assignee.get('name', '')}")

            results.append({
                "id": card.get("id"),
                "title": card.get("title"),
                "text": "\n".join(text_parts),
            })

        return results
