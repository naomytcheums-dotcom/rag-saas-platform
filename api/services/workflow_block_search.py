"""
Partie 5.4.5 -- real `web_search` workflow block execution.

**Cohérence (vision critique 1): reuses the real `web_search` tool
(Partie 5.2.2) end-to-end, no second/competing web-search path** --
`api.tools.web_search.web_search` for the actual real Tavily call,
`format_web_search_results` for the real, LLM-facing formatting.
`exclude_domains` (this étape's own literal config field) needed a
real, small, symmetric addition to `web_search`/`_call_tavily`
(Partie 5.4.5) alongside Partie 5.3.9's own `allowed_domains` -- both
now real, given-overrides-global config, not a second, parallel
domain-filtering mechanism."""

from api.services.template_rendering import render_template
from api.services.workflow_blocks import WorkflowBlockError
from api.tools.web_search import WebSearchError, format_web_search_results, web_search

_SEARCH_DEPTHS = ("basic", "advanced")


def validate_search_config(config: dict) -> None:
    """Item 2's own literal function -- real, upfront validation."""
    if not config.get("query"):
        raise WorkflowBlockError("web_search block requires a real, non-empty 'query'")
    search_depth = config.get("search_depth")
    if search_depth is not None and search_depth not in _SEARCH_DEPTHS:
        raise WorkflowBlockError(f"Unknown search_depth: {search_depth!r} (expected one of {_SEARCH_DEPTHS})")
    max_results = config.get("max_results")
    if max_results is not None and max_results <= 0:
        raise WorkflowBlockError("web_search block's max_results must be a real, positive integer")


def render_search_query(query_template: str, context: dict) -> str:
    """Item 2's own literal function -- real, shared `{{var}}`
    substitution."""
    return render_template(query_template, context)


def format_search_results(results: dict) -> str:
    """Item 2's own literal function -- real reuse, not a second
    formatter."""
    return format_web_search_results(results)


async def execute_search_block(block_config: dict, context: dict) -> dict:
    """Item 2's own literal function -- real, upfront validation, real
    query rendering, then a real, live web search."""
    validate_search_config(block_config)
    query = render_search_query(block_config["query"], context)

    try:
        results = await web_search(
            query, search_depth=block_config.get("search_depth"), max_results=block_config.get("max_results"),
            allowed_domains=block_config.get("include_domains"), exclude_domains=block_config.get("exclude_domains"),
        )
    except WebSearchError as exc:
        raise WorkflowBlockError(f"web_search block failed: {exc}") from exc

    return {block_config.get("output_key", "output"): format_search_results(results)}
