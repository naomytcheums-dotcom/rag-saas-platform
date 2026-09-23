"""
Phase 5, Étape 6 -- closes the exact, precisely-named gap
`api.services.agent_tools`'s own module docstring already documented:
6 of the 12 real `AGENT_TOOL_CATALOG` tools (`github_get_repo`,
`github_list_issues`, `execute_sql_query`, `calendar_list_events`,
`calendar_create_event`, `email_read`) were real, callable functions in
`api/tools/` but were never wrapped into `api.services.tools`' shared
`ToolSpec` registry -- meaning the new real function-calling loop
(`api.services.agent_orchestrator`) could never actually reach them,
regardless of whether an agent's own config selected them.

Five of the six are wrapped here as real, static, importable `ToolSpec`
constants and registered at import time (`register_tool`, finally
used -- it existed since Partie 5.1.2 with zero real callers before
this). `execute_sql_query` is the deliberate exception: its own real
signature takes `db: AsyncSession` and `organization_id: uuid.UUID`,
neither of which the LLM must ever be allowed to supply (an LLM-
controlled `organization_id` would be a real cross-tenant data leak) --
`build_sql_query_tool` below builds a real, per-run `ToolSpec` with
both bound by closure, exposing only `query`/`max_rows` to the LLM.
`AgentOrchestrator` calls it fresh for every run that has real `db`/
`organization_id` in scope, rather than a static, globally-registered
tool that would leak whichever organization built it first.

Also adds `http_request`, one of the étape's own literal spec's named
builtin tools (section 3.2) with no existing implementation anywhere
in `api/tools/` -- real, using this codebase's own canonical
`ssrf_safe_client()` (api/services/url_fetching.py), the same SSRF
protection already reused by the workflow engine's HTTP block and
custom webhook tools, never a second, parallel HTTP path.
"""

import json
import uuid

from sqlalchemy.ext.asyncio import AsyncSession

from api.tools.calendar_tools import calendar_create_event, calendar_list_events
from api.tools.email_tools import email_read
from api.tools.github_tools import github_get_repo, github_list_issues
from api.tools.sql_tool import execute_sql_query
from api.services.tools import ToolSpec, register_tool
from api.services.url_fetching import ssrf_safe_client


async def _github_get_repo_handler(owner: str, repo: str) -> str:
    return json.dumps(await github_get_repo(owner, repo), default=str)


async def _github_list_issues_handler(owner: str, repo: str, state: str = "all") -> str:
    return json.dumps(await github_list_issues(owner, repo, state=state), default=str)


async def _calendar_list_events_handler(provider: str, start_date: str, end_date: str) -> str:
    return json.dumps(await calendar_list_events(provider, start_date, end_date), default=str)


async def _calendar_create_event_handler(provider: str, title: str, start_time: str, end_time: str) -> str:
    return json.dumps(await calendar_create_event(provider, title, start_time, end_time), default=str)


async def _email_read_handler(provider: str, folder: str = "inbox", limit: int = 10) -> str:
    return json.dumps(await email_read(provider, folder=folder, limit=limit), default=str)


GITHUB_GET_REPO_TOOL = ToolSpec(
    name="github_get_repo", description="Fetch a real GitHub repository's metadata (stars, forks, description, default branch).",
    parameters={
        "owner": {"type": "string", "description": "The repository owner (user or organization)"},
        "repo": {"type": "string", "description": "The repository name"},
    },
    capability_tags=("github", "repository", "metadata"), handler=_github_get_repo_handler,
)

GITHUB_LIST_ISSUES_TOOL = ToolSpec(
    name="github_list_issues", description="List a real GitHub repository's issues.",
    parameters={
        "owner": {"type": "string", "description": "The repository owner (user or organization)"},
        "repo": {"type": "string", "description": "The repository name"},
        "state": {"type": "string", "description": "Issue state: 'open', 'closed', or 'all'"},
    },
    capability_tags=("github", "issues"), handler=_github_list_issues_handler,
)

CALENDAR_LIST_EVENTS_TOOL = ToolSpec(
    name="calendar_list_events", description="List a real calendar's events in a date range.",
    parameters={
        "provider": {"type": "string", "description": "Calendar provider: 'google' or 'outlook'"},
        "start_date": {"type": "string", "description": "Start of the range, ISO 8601"},
        "end_date": {"type": "string", "description": "End of the range, ISO 8601"},
    },
    capability_tags=("calendar", "events"), handler=_calendar_list_events_handler,
)

CALENDAR_CREATE_EVENT_TOOL = ToolSpec(
    name="calendar_create_event", description="Create a real calendar event.",
    parameters={
        "provider": {"type": "string", "description": "Calendar provider: 'google' or 'outlook'"},
        "title": {"type": "string", "description": "Event title"},
        "start_time": {"type": "string", "description": "Start time, ISO 8601"},
        "end_time": {"type": "string", "description": "End time, ISO 8601"},
    },
    capability_tags=("calendar", "events", "create"), handler=_calendar_create_event_handler,
)

EMAIL_READ_TOOL = ToolSpec(
    name="email_read", description="Read messages from a real email inbox.",
    parameters={
        "provider": {"type": "string", "description": "Email provider: 'gmail' or 'outlook'"},
        "folder": {"type": "string", "description": "Folder to read from, e.g. 'inbox'"},
        "limit": {"type": "integer", "description": "Maximum number of messages to return"},
    },
    capability_tags=("email", "read"), handler=_email_read_handler,
)


async def _http_request_handler(url: str, method: str = "GET") -> str:
    async with ssrf_safe_client() as client:
        response = await client.request(method.upper(), url)
    return json.dumps({"status_code": response.status_code, "body": response.text[:4000]})


HTTP_REQUEST_TOOL = ToolSpec(
    name="http_request", description="Make a real HTTP request to a URL (GET/POST/PUT/PATCH/DELETE), SSRF-protected.",
    parameters={
        "url": {"type": "string", "description": "The URL to request"},
        "method": {"type": "string", "description": "HTTP method, e.g. 'GET' or 'POST'"},
    },
    capability_tags=("http", "web"), handler=_http_request_handler,
)

for _tool in (GITHUB_GET_REPO_TOOL, GITHUB_LIST_ISSUES_TOOL, CALENDAR_LIST_EVENTS_TOOL, CALENDAR_CREATE_EVENT_TOOL, EMAIL_READ_TOOL, HTTP_REQUEST_TOOL):
    register_tool(_tool)


def build_sql_query_tool(db: AsyncSession, organization_id: uuid.UUID) -> ToolSpec:
    """Real, per-run `ToolSpec` for `execute_sql_query` -- `db`/
    `organization_id` are bound by closure, never LLM-controllable
    arguments, so a run can never query a different organization's
    data no matter what the LLM's own tool-call arguments say."""

    async def _handler(query: str, max_rows: int | None = None) -> str:
        return json.dumps(await execute_sql_query(db, query, organization_id, max_rows=max_rows), default=str)

    return ToolSpec(
        name="execute_sql_query", description="Execute a real, read-only SQL query against the organization's own allow-listed tables.",
        parameters={
            "query": {"type": "string", "description": "The read-only SQL query to execute"},
            "max_rows": {"type": "integer", "description": "Maximum number of rows to return"},
        },
        capability_tags=("data", "sql"), handler=_handler,
    )
