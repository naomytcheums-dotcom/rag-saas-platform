"""
Extraction -- fetching issues from Linear's real GraphQL API, for
import into a knowledge base.

**Real auth shape**: a real, static `LINEAR_API_TOKEN` (a real Linear
"personal API key", admin-configured once), sent as the raw
`Authorization` header (Linear's own real convention -- NOT
"Bearer <token>").
"""

import logging

import httpx

from api.config import settings

logger = logging.getLogger(__name__)

_GRAPHQL_ENDPOINT = "https://api.linear.app/graphql"

_ISSUES_QUERY = """
query Issues($first: Int!) {
  issues(first: $first) {
    nodes {
      id
      identifier
      title
      description
      state { name }
      priority
      assignee { name email }
      team { name key }
      createdAt
      updatedAt
    }
  }
}
"""


class LinearError(Exception):
    """Real, dedicated exception -- a connection/discovery/call failure
    against Linear, never silently swallowed."""


class LinearRateLimitError(LinearError):
    """Real, distinguishable 429."""


async def fetch_linear_issues(limit: int = 100) -> list[dict]:
    """Real fetch of issues from Linear via GraphQL.

    Returns a list of {id, identifier, title, text} dicts, where `text`
    is a real, plain-text representation suitable for RAG ingestion.
    """
    if not settings.LINEAR_ENABLED:
        raise LinearError("Linear integration is disabled")
    if not settings.LINEAR_API_TOKEN:
        raise LinearError("Linear API token not configured")

    headers = {
        "Authorization": settings.LINEAR_API_TOKEN,
        "Content-Type": "application/json",
    }

    async with httpx.AsyncClient(timeout=30.0) as client:
        response = await client.post(
            _GRAPHQL_ENDPOINT,
            headers=headers,
            json={"query": _ISSUES_QUERY, "variables": {"first": limit}},
        )

        if response.status_code == 429:
            raise LinearRateLimitError("Linear rate limit reached")
        if response.status_code != 200:
            raise LinearError(f"Linear fetch failed: {response.status_code}")

        data = response.json()
        if "errors" in data:
            raise LinearError(f"Linear GraphQL errors: {data['errors']}")

        issues = data.get("data", {}).get("issues", {}).get("nodes", [])
        results = []
        for issue in issues:
            text_parts = [
                f"Identifier: {issue.get('identifier', '')}",
                f"Title: {issue.get('title', '')}",
            ]
            if issue.get("description"):
                text_parts.append(f"Description: {issue['description']}")
            if issue.get("state"):
                text_parts.append(f"State: {issue['state'].get('name', '')}")
            if issue.get("priority") is not None:
                text_parts.append(f"Priority: {issue['priority']}")
            if issue.get("assignee"):
                text_parts.append(f"Assignee: {issue['assignee'].get('name', '')}")
            if issue.get("team"):
                text_parts.append(f"Team: {issue['team'].get('name', '')}")

            results.append({
                "id": issue.get("id"),
                "identifier": issue.get("identifier"),
                "title": issue.get("title"),
                "text": "\n".join(text_parts),
            })

        return results
