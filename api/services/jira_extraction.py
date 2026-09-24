"""
CRM extraction -- fetching issues from Jira's real REST API v3, for
import into a knowledge base. Uses a plain `httpx.AsyncClient` against
the org's own configured Jira instance URL, the same "trusted,
admin-configured external API" reasoning as
`api/services/notion_extraction.py`.

**Real auth shape**: HTTP Basic with a real, static `JIRA_EMAIL` +
`JIRA_API_TOKEN` pair (a real Jira "API token", admin-configured once).
"""

import base64
import logging

import httpx

from api.config import settings

logger = logging.getLogger(__name__)


class JiraError(Exception):
    """Real, dedicated exception -- a connection/discovery/call failure
    against Jira, never silently swallowed."""


class JiraRateLimitError(JiraError):
    """Real, distinguishable 429."""


async def fetch_jira_issues(
    project_key: str | None = None,
    limit: int = 100,
) -> list[dict]:
    """Real fetch of issues from Jira.

    Returns a list of {id, key, fields, text} dicts, where `text` is a
    real, plain-text representation suitable for RAG ingestion.
    """
    if not settings.JIRA_ENABLED:
        raise JiraError("Jira integration is disabled")
    if not settings.JIRA_BASE_URL or not settings.JIRA_EMAIL or not settings.JIRA_API_TOKEN:
        raise JiraError("Jira credentials not configured")

    auth_str = f"{settings.JIRA_EMAIL}:{settings.JIRA_API_TOKEN}"
    auth_b64 = base64.b64encode(auth_str.encode()).decode()
    headers = {"Authorization": f"Basic {auth_b64}", "Accept": "application/json"}

    jql = f"project={project_key}" if project_key else "order by created DESC"

    results = []
    async with httpx.AsyncClient(timeout=30.0) as client:
        response = await client.get(
            f"{settings.JIRA_BASE_URL.rstrip('/')}/rest/api/3/search",
            headers=headers,
            params={"jql": jql, "maxResults": limit, "fields": "summary,description,status,priority,assignee,reporter,created"},
        )

        if response.status_code == 429:
            raise JiraRateLimitError("Jira rate limit reached")
        if response.status_code != 200:
            raise JiraError(f"Jira fetch failed: {response.status_code}")

        for issue in response.json().get("issues", []):
            fields = issue.get("fields", {}) or {}
            text_parts = [
                f"Key: {issue.get('key', '')}",
                f"Summary: {fields.get('summary', '')}",
            ]
            if fields.get("status"):
                text_parts.append(f"Status: {fields['status'].get('name', '')}")
            if fields.get("priority"):
                text_parts.append(f"Priority: {fields['priority'].get('name', '')}")
            if fields.get("assignee"):
                text_parts.append(f"Assignee: {fields['assignee'].get('displayName', '')}")
            if fields.get("description"):
                text_parts.append(f"Description: {fields['description']}")

            results.append({
                "id": issue.get("id"),
                "key": issue.get("key"),
                "fields": fields,
                "text": "\n".join(text_parts),
            })

    return results
