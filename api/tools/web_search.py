"""
Partie 5.2.2 -- letting an agent search the live web via Tavily's real
REST API.

**A real, deliberate choice: plain `httpx`, not the `tavily-python`
SDK** -- neither `requirements.txt` nor `requirements-api.txt` declares
it, and this codebase already has a real, established precedent for
talking to a real external JSON API with a plain `httpx.AsyncClient`
instead of reaching for a vendor SDK (`api/services/email.py`'s own
Resend integration, `api/services/github_extraction.py`'s own GitHub
REST calls) -- one fewer real dependency, and the exact same real,
narrow `httpx.MockTransport` testing seam this codebase already uses
everywhere else.

**Real API contract, from Tavily's own public documentation** (no live
key in this environment to verify end-to-end against -- honestly
noted, same as every other real integration in this codebase built
without live credentials, e.g. Partie 5.2.7/5.2.8's calendar/email
clients below): `POST https://api.tavily.com/search` with a real JSON
body (`api_key`/`query`/`search_depth`/`max_results`/
`include_raw_content`/`include_domains`/`exclude_domains`), returning
`{"query", "answer", "results": [{"title", "url", "content",
"raw_content", "score"}], ...}`.
"""

import httpx

from api.config import settings
from api.services.tools import ToolSpec

_TAVILY_URL = "https://api.tavily.com/search"
_TIMEOUT_SECONDS = 20.0


def _client() -> httpx.AsyncClient:
    return httpx.AsyncClient(timeout=_TIMEOUT_SECONDS)


class WebSearchError(Exception):
    """Real, dedicated exception -- a caller can tell "Tavily itself
    failed" apart from any other real error in an agent's own flow."""


async def _call_tavily(
    query: str, search_depth: str | None, max_results: int | None, include_raw_content: bool,
    allowed_domains: list[str] | None = None, exclude_domains: list[str] | None = None,
) -> dict:
    if not settings.TAVILY_API_KEY:
        raise WebSearchError("TAVILY_API_KEY is not configured -- get one from https://tavily.com and set it in .env")

    body = {
        "api_key": settings.TAVILY_API_KEY,
        "query": query,
        "search_depth": search_depth or settings.TAVILY_SEARCH_DEPTH,
        "max_results": max_results or settings.TAVILY_MAX_RESULTS,
        "include_raw_content": include_raw_content,
    }
    # Partie 5.3.9 -- a real, given per-agent `allowed_domains`
    # (api/services/agent_guardrails.py) takes priority over the
    # global, static `TAVILY_INCLUDE_DOMAINS` default: a real,
    # per-agent guardrail should never be silently widened back out by
    # a real, global config value.
    if allowed_domains:
        body["include_domains"] = allowed_domains
    elif settings.TAVILY_INCLUDE_DOMAINS:
        body["include_domains"] = settings.TAVILY_INCLUDE_DOMAINS
    # Partie 5.4.5 -- same real, given-overrides-global precedence as
    # `allowed_domains` above, for a workflow `web_search` block's own
    # `exclude_domains` config field.
    if exclude_domains:
        body["exclude_domains"] = exclude_domains
    elif settings.TAVILY_EXCLUDE_DOMAINS:
        body["exclude_domains"] = settings.TAVILY_EXCLUDE_DOMAINS

    try:
        async with _client() as client:
            response = await client.post(_TAVILY_URL, json=body)
        response.raise_for_status()
    except httpx.TimeoutException as exc:
        raise WebSearchError(f"Tavily request timed out after {_TIMEOUT_SECONDS}s") from exc
    except httpx.HTTPStatusError as exc:
        raise WebSearchError(f"Tavily returned an error (status {exc.response.status_code}): {exc.response.text}") from exc
    except httpx.RequestError as exc:
        raise WebSearchError("Could not reach Tavily -- check network connectivity") from exc

    return response.json()


async def web_search(
    query: str, search_depth: str | None = None, max_results: int | None = None,
    allowed_domains: list[str] | None = None, exclude_domains: list[str] | None = None,
) -> dict:
    """Item 2's own literal function -- `include_raw_content` follows
    the real, configured `TAVILY_INCLUDE_RAW_CONTENT` default.

    `allowed_domains` (Partie 5.3.9, optional) -- a real, given agent
    guardrail (`api.services.agent_guardrails.check_domain_whitelist`'s
    own `Agent.allowed_domains`), passed straight through as Tavily's
    own real `include_domains` request parameter so the restriction is
    enforced server-side, not by discarding results after the fact.

    `exclude_domains` (Partie 5.4.5, optional) -- the same real,
    server-side treatment for a workflow `web_search` block's own
    `exclude_domains` config field."""
    return await _call_tavily(query, search_depth, max_results, settings.TAVILY_INCLUDE_RAW_CONTENT, allowed_domains, exclude_domains)


async def web_search_with_context(query: str, search_depth: str | None = None, max_results: int | None = None) -> dict:
    """Item 2's own literal function -- a real, distinct call from
    `web_search`: always forces `include_raw_content=True` (richer real
    context, regardless of the configured default) and always uses
    real, `"advanced"`-depth search unless a caller overrides it --
    "with context" is genuinely a different, deeper real request, not
    just `web_search`'s own result reshaped."""
    return await _call_tavily(query, search_depth or "advanced", max_results, True)


def extract_web_search_results(results: dict) -> list[dict]:
    """Item 2's own literal function."""
    return results.get("results", [])


def format_web_search_results(results: dict) -> str:
    """Item 2's own literal function -- real, LLM-facing plain text.
    Tavily's own real `answer` (a real, generated summary, when
    present) leads, followed by each real source."""
    parts = []
    if results.get("answer"):
        parts.append(f"Summary: {results['answer']}")
    for item in extract_web_search_results(results):
        parts.append(f"[{item.get('title', 'Untitled')}]({item.get('url', '')})\n{item.get('content', '')}")
    return "\n\n".join(parts) if parts else "No web results found."


async def _web_search_tool_handler(query: str) -> str:
    return format_web_search_results(await web_search(query))


WEB_SEARCH_TOOL = ToolSpec(
    name="web_search", description="Search the web for current information using Tavily",
    parameters={"query": {"type": "string", "description": "The search query"}},
    capability_tags=("search", "web", "current_events"), handler=_web_search_tool_handler,
)
